"""
Exemple d'intégration complète du SmartPool adapter avec omni-cache.

Cet exemple montre comment utiliser votre module smartpool avec omni-cache
pour créer des pools d'objets sophistiqués.
"""

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from omni_cache.adapters.smartpool.smartpool import (
    SmartPoolAdapter,
    SmartPoolAdapterConfig,
    create_connection_pool,
)
from omni_cache.core.adapter_registry import ManagerConfig
from omni_cache.core.manager import CacheManager


class SqliteConnectionWrapper:
    """Wrapper for sqlite3.Connection to allow weak referencing."""

    def __init__(self, conn: sqlite3.Connection):
        self.connection = conn

    def __getattr__(self, name):
        """Delegate attribute access to the underlying connection."""
        return getattr(self.connection, name)

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # Connection lifecycle managed by SmartPool


class WeakRefWrapper:
    """Generic wrapper for objects that don't support weak referencing."""

    def __init__(self, obj: Any):
        self.obj = obj

    def __getattr__(self, name):
        """Delegate attribute access to the underlying object."""
        return getattr(self.obj, name)

    def __enter__(self):
        return self.obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # Object lifecycle managed by SmartPool


def exemple_pool_base_donnees():
    """
    Exemple complet d'un pool de connexions de base de données
    utilisant SmartPool via omni-cache.
    """
    print("=== Exemple Pool Base de Données avec SmartPool ===")

    # Fonctions pour gérer les connexions DB
    def create_db_connection():
        """Crée une nouvelle connexion à la base de données."""
        print(f"[{threading.current_thread().name}] Création nouvelle connexion DB")
        conn = sqlite3.connect(":memory:")
        # Configuration initiale
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
        conn.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)", ("Alice", "alice@example.com")
        )
        conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Bob", "bob@example.com"))
        conn.commit()
        return SqliteConnectionWrapper(conn)

    def reset_db_connection(wrapper):
        """Remet la connexion DB dans un état propre."""
        print(f"[{threading.current_thread().name}] Reset connexion DB")
        try:
            wrapper.connection.rollback()  # Annuler toutes les transactions en cours
        except Exception:
            pass

    def validate_db_connection(wrapper):
        """Valide qu'une connexion DB est encore utilisable."""
        try:
            wrapper.connection.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def destroy_db_connection(wrapper):
        """Nettoie une connexion DB."""
        print(f"[{threading.current_thread().name}] Destruction connexion DB")
        try:
            wrapper.connection.close()
        except Exception:
            pass

    # Configuration du SmartPool adapter
    config = SmartPoolAdapterConfig(
        name="db_connection_pool",
        factory_function=create_db_connection,
        initial_size=3,
        max_size=10,
        min_size=1,
        memory_preset="HIGH_THROUGHPUT",  # Optimisé pour accès fréquents
        enable_background_cleanup=True,
        enable_performance_metrics=True,
        enable_auto_tuning=True,
        auto_tuning_interval=60.0,  # Auto-tuning toutes les minutes
        max_age_seconds=300.0,  # Connexions expirées après 5 minutes
        max_idle_time=120.0,  # Inactives après 2 minutes
        extra_config={
            "reset_func": reset_db_connection,
            "validate_func": validate_db_connection,
            "destroy_func": destroy_db_connection,
        },
    )

    # Créer et configurer le manager omni-cache
    manager_config = ManagerConfig(
        default_adapter="smartpool_db", auto_connect=True, enable_global_stats=True
    )
    manager = CacheManager(manager_config)

    # Créer et enregistrer l'adapter SmartPool
    adapter = SmartPoolAdapter(config)
    manager.register_adapter("smartpool_db", adapter)

    try:
        print("Connexion de l'adapter...")
        success = adapter.connect()
        print(f"Connexion: {'✓' if success else '✗'}")

        if not success:
            print("Échec de connexion, arrêt de l'exemple")
            return

        # Test 1: Utilisation basique avec context manager
        print("\n--- Test 1: Utilisation basique ---")
        with adapter.borrow() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            print(f"Nombre d'utilisateurs: {count}")

        # Test 2: Utilisation concurrente
        print("\n--- Test 2: Utilisation concurrente ---")

        def worker_task(worker_id: int) -> dict[str, Any]:
            """Tâche worker qui utilise une connexion DB."""
            results = []
            for i in range(3):
                try:
                    with adapter.borrow() as conn:
                        cursor = conn.cursor()
                        # Simuler une requête
                        cursor.execute("SELECT name FROM users WHERE id = ?", (i % 2 + 1,))
                        result = cursor.fetchone()
                        results.append(
                            f"Worker{worker_id}-Task{i}: {result[0] if result else 'None'}"
                        )
                        time.sleep(0.1)  # Simuler du travail
                except Exception as e:
                    results.append(f"Worker{worker_id}-Task{i}: Error - {e}")
            return {
                "worker_id": worker_id,
                "results": results,
                "thread_name": threading.current_thread().name,
            }

        # Exécuter plusieurs workers en parallèle
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="DBWorker") as executor:
            futures = [executor.submit(worker_task, i) for i in range(4)]

            for future in as_completed(futures):
                worker_result = future.result()
                print(f"Worker {worker_result['worker_id']} ({worker_result['thread_name']}):")
                for result in worker_result["results"]:
                    print(f"  - {result}")

        # Test 3: Statistiques et monitoring
        print("\n--- Test 3: Statistiques et monitoring ---")

        # Statistiques de base
        backend_info = adapter.get_backend_info()
        print(f"Taille actuelle du pool: {backend_info['current_size']}")
        print(f"Objets actifs: {backend_info['active_objects']}")
        print(f"Objets totaux: {backend_info['total_objects']}")

        # Statistiques détaillées
        detailed_stats = adapter.get_detailed_stats()
        if detailed_stats:
            hits = detailed_stats.get("hits", 0)
            misses = detailed_stats.get("misses", 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            print(f"Taux de réussite du cache: {hit_rate:.1f}% ({hits}/{total})")

        # Rapport de performance
        if config.enable_performance_metrics:
            perf_report = adapter.get_performance_report(detailed=False)
            if perf_report:
                print(f"Rapport de performance: {perf_report}")

        # Test 4: Health check
        print("\n--- Test 4: Health check ---")
        is_healthy = adapter.health_check()
        print(f"Pool en bonne santé: {'✓' if is_healthy else '✗'}")

        # Test 5: Nettoyage forcé
        print("\n--- Test 5: Nettoyage ---")
        cleaned_count = adapter.force_cleanup()
        print(f"Objets nettoyés: {cleaned_count}")

    finally:
        # Nettoyage
        print("\nDéconnexion...")
        adapter.disconnect()
        print("Exemple terminé.")


def exemple_integration_factory_omnicache():
    """
    Exemple d'intégration avec le système de factory d'omni-cache.
    """
    print("\n=== Intégration avec Factory omni-cache ===")

    from omni_cache import CacheBackend, create_adapter

    # Fonction simple pour créer des objets
    def create_expensive_object(size: int = 1024):
        """Simule la création d'un objet coûteux."""
        print(f"[{threading.current_thread().name}] Création objet coûteux (taille: {size})")
        time.sleep(0.1)  # Simule le coût de création
        obj = {
            "data": b"x" * size,
            "created_at": time.time(),
            "size": size,
            "id": id(object()),  # ID unique
        }
        return WeakRefWrapper(obj)

    def reset_expensive_object(wrapper):
        """Remet l'objet coûteux dans un état propre."""
        obj = wrapper.obj
        obj["last_reset"] = time.time()
        # Nettoyer des données temporaires si nécessaire
        obj.pop("temp_data", None)

    try:
        # Créer adapter via le système de factory omni-cache
        adapter = create_adapter(
            CacheBackend.SMARTPOOL,
            {
                "name": "expensive_objects",
                "factory_function": create_expensive_object,
                "factory_kwargs": {"size": 2048},
                "initial_size": 2,
                "max_size": 8,
                "memory_preset": "BALANCED",
                "enable_auto_tuning": True,
                "extra_config": {
                    "reset_func": reset_expensive_object,
                },
            },
        )

        # Connecter
        if not adapter.connect():
            print("Échec connexion adapter factory")
            return

        print("Adapter créé via factory omni-cache ✓")

        # Utilisation
        print("\nUtilisation via factory:")
        for i in range(5):
            with adapter.borrow() as wrapper:
                obj = wrapper.obj
                print(
                    f"Objet {i}: ID={obj['id']}, taille={obj['size']}, "
                    f"créé à {obj['created_at']:.1f}"
                )

        # Statistiques
        info = adapter.get_backend_info()
        print(
            f"\nPool via factory - Taille: {info['current_size']}, Total: {info['total_objects']}"
        )

    finally:
        if "adapter" in locals():
            adapter.disconnect()


def exemple_pool_connexions_http():
    """
    Exemple de pool de sessions HTTP avec SmartPool.
    """
    print("\n=== Pool Sessions HTTP ===")

    try:
        import requests
    except ImportError:
        print("requests non disponible, exemple HTTP ignoré")
        return

    def create_http_session():
        """Crée une session HTTP configurée."""
        print(f"[{threading.current_thread().name}] Création session HTTP")
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "SmartPool-Example/1.0", "Accept": "application/json"}
        )
        session.timeout = 10
        return WeakRefWrapper(session)

    def reset_http_session(wrapper):
        """Remet la session HTTP en état propre."""
        session = wrapper.obj
        session.cookies.clear()
        session.auth = None

    def validate_http_session(wrapper):
        """Valide qu'une session HTTP est utilisable."""
        session = wrapper.obj
        try:
            # Test simple de la session
            return hasattr(session, "get") and callable(session.get)
        except Exception:
            return False

    # Créer adapter avec fonction de convenance
    adapter = create_connection_pool(
        connection_factory=create_http_session,
        pool_size=2,
        max_pool_size=5,
        name="http_sessions",
        extra_config={
            "reset_func": reset_http_session,
            "validate_func": validate_http_session,
        },
    )

    try:
        if not adapter.connect():
            print("Échec connexion adapter HTTP")
            return

        print("Pool sessions HTTP créé ✓")

        # Test d'utilisation
        test_urls = [
            "https://httpbin.org/json",
            "https://httpbin.org/status/200",
        ]

        def make_request(url):
            """Fait une requête HTTP avec pooling."""
            try:
                with adapter.borrow() as wrapper:
                    session = wrapper.obj
                    response = session.get(url, timeout=5)
                    return f"{url}: {response.status_code}"
            except Exception as e:
                return f"{url}: Error - {type(e).__name__}"

        print("\nRequêtes HTTP concurrentes:")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(make_request, url) for url in test_urls]
            for future in as_completed(futures):
                print(f"  - {future.result()}")

        # Statistiques finales
        info = adapter.get_backend_info()
        print(f"\nPool HTTP - Actuel: {info['current_size']}, Actifs: {info['active_objects']}")

    finally:
        adapter.disconnect()


def main():
    """Point d'entrée principal des exemples."""
    print("Exemples d'intégration SmartPool avec omni-cache")
    print("=" * 60)

    try:
        # Exemple principal
        exemple_pool_base_donnees()

        # Exemple intégration factory
        exemple_integration_factory_omnicache()

        # Exemple sessions HTTP
        exemple_pool_connexions_http()

        print("\n" + "=" * 60)
        print("Tous les exemples terminés avec succès ✓")

    except ImportError as e:
        print(f"Module manquant: {e}")
        print("Assurez-vous que smartpool et omni-cache sont installés")
    except Exception as e:
        print(f"Erreur dans les exemples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
