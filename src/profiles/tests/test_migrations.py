from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("profiles", "0001_initial")]
BACKFILL = [("profiles", "0002_create_missing_profiles")]


class CreateMissingProfilesMigrationTests(TransactionTestCase):
    # TransactionTestCase: SQLite can't alter the schema inside TestCase's
    # transaction.

    def tearDown(self):
        # Leave the schema at the latest migrations for the other tests.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_users_who_existed_before_get_one_profile(self):
        executor = MigrationExecutor(connection)
        self.assertIn(BACKFILL[0], executor.loader.graph.nodes)
        executor.migrate(BEFORE)
        old_apps = executor.loader.project_state(BEFORE).apps
        User = old_apps.get_model(settings.AUTH_USER_MODEL)
        OldProfile = old_apps.get_model("profiles", "Profile")
        # Historical models fire no signals, so neither user gets a profile here.
        old = User.objects.create(username="old")
        has = User.objects.create(username="has")
        OldProfile.objects.create(user=has, name="Has One")

        executor.loader.build_graph()
        executor.migrate(BACKFILL)

        Profile = executor.loader.project_state(BACKFILL).apps.get_model(
            "profiles", "Profile"
        )
        self.assertEqual(Profile.objects.filter(user_id=old.pk).count(), 1)
        backfilled = Profile.objects.get(user_id=old.pk)
        self.assertEqual((backfilled.name, backfilled.cohort), ("", ""))
        self.assertFalse(backfilled.focus_areas.exists())
        self.assertEqual(Profile.objects.filter(user_id=has.pk).count(), 1)
        self.assertEqual(Profile.objects.get(user_id=has.pk).name, "Has One")
