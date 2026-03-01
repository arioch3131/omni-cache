#!/usr/bin/env python3
"""
Script de diagnostic approfondi pour SmartPool
"""

import logging
import time

from omni_cache import create_adapter, setup
from omni_cache.core.interfaces import CacheBackend

# Configuration du logging pour voir tous les détails
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def create_simple_data_object():
    """Factory function qui crée des objets de données simples."""
    return {
        "data": f"test_data_{time.time()}",
        "timestamp": time.time(),
        "id": hash(time.time()) % 1000000,
    }


def main():
    print("🔍 DIAGNOSTIC SMARTPOOL APPROFONDI")
    print("=" * 50)

    # Setup manager
    setup(log_level="DEBUG")

    # Configuration SmartPool
    smartpool_config = {
        "name": "smartpool_debug",
        "factory_function": create_simple_data_object,
        "initial_size": 5,
        "max_size": 20,
        "enable_auto_tuning": True,
        "enable_performance_metrics": True,
        "memory_preset": "HIGH_THROUGHPUT",
    }

    try:
        print("\n1. 🔧 Création de l'adapter...")
        smartpool_adapter = create_adapter(CacheBackend.SMARTPOOL, smartpool_config)

        print("\n2. 📡 Test de connexion...")
        connect_result = smartpool_adapter.connect()
        print(f"   Connexion: {'✅ Réussie' if connect_result else '❌ Échouée'}")
        print(f"   Est connecté: {'✅ Oui' if smartpool_adapter.is_connected() else '❌ Non'}")

        if not connect_result:
            print("❌ Impossible de continuer sans connexion")
            return

        print("\n3. 🔍 Inspection du pool interne...")
        # Accéder au pool SmartPool directement
        if hasattr(smartpool_adapter, "_pool") and smartpool_adapter._pool:
            pool = smartpool_adapter._pool
            print(f"   Pool type: {type(pool)}")

            # Obtenir les stats du pool
            try:
                stats = pool.get_stats()
                print(f"   Stats du pool: {stats}")
            except Exception as e:
                print(f"   ❌ Erreur stats: {e}")

            # Obtenir le statut de santé
            try:
                health = pool.get_health_status()
                print(f"   Statut de santé: {health}")
            except Exception as e:
                print(f"   ❌ Erreur health status: {e}")
        else:
            print("   ❌ Pool interne non accessible")

        print("\n4. 🎯 Tests d'opérations basiques...")
        # Test de base: borrow/release
        for i in range(3):
            try:
                with smartpool_adapter.borrow() as obj:
                    print(f"   Test {i + 1}: Object emprunté - {type(obj)} - {obj}")
                    if hasattr(obj, "data"):
                        obj.data = f"test_operation_{i}"
                print(f"   Test {i + 1}: ✅ Réussi")
            except Exception as e:
                print(f"   Test {i + 1}: ❌ Échoué - {e}")

        print("\n5. 📊 Vérification des stats après opérations...")
        if hasattr(smartpool_adapter, "_pool") and smartpool_adapter._pool:
            try:
                stats_after = smartpool_adapter._pool.get_stats()
                health_after = smartpool_adapter._pool.get_health_status()
                print(f"   Stats après: {stats_after}")
                print(f"   Santé après: {health_after}")
            except Exception as e:
                print(f"   ❌ Erreur: {e}")

        print("\n6. 🏥 Test du health check...")
        health_result = smartpool_adapter.health_check()
        print(f"   Health check: {'✅ Sain' if health_result else '❌ Problème'}")

        print("\n7. 📋 Informations du backend...")
        try:
            backend_info = smartpool_adapter.get_backend_info()
            print(f"   Backend info: {backend_info}")
        except Exception as e:
            print(f"   ❌ Erreur backend info: {e}")

        print("\n8. 🔄 Test avec plus d'opérations...")
        # Faire beaucoup plus d'opérations
        operations_count = 20
        success_count = 0

        for i in range(operations_count):
            try:
                with smartpool_adapter.borrow() as obj:
                    if hasattr(obj, "data"):
                        obj.data = f"stress_test_{i}"
                success_count += 1
            except Exception as e:
                print(f"   Opération {i}: ❌ {e}")

        print(f"   Opérations réussies: {success_count}/{operations_count}")

        print("\n9. 🏥 Health check final...")
        final_health = smartpool_adapter.health_check()
        print(f"   Health check final: {'✅ Sain' if final_health else '❌ Problème'}")

        # Stats finales détaillées
        if hasattr(smartpool_adapter, "_pool") and smartpool_adapter._pool:
            try:
                final_stats = smartpool_adapter._pool.get_stats()
                final_health_status = smartpool_adapter._pool.get_health_status()
                print(f"   Stats finales: {final_stats}")
                print(f"   Santé finale: {final_health_status}")
            except Exception as e:
                print(f"   ❌ Erreur stats finales: {e}")

    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 50)
    print("🏁 DIAGNOSTIC TERMINÉ")


if __name__ == "__main__":
    main()
