# Generated manually to fix User foreign key type mismatch

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
        ("authentication", "0003_remove_user_avatar_url_remove_user_date_joined_and_more"),
    ]

    operations = [
        # Remove old foreign key constraint
        migrations.RunSQL(
            sql='ALTER TABLE "subscriptions" DROP CONSTRAINT IF EXISTS "subscriptions_user_id_fkey";',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Clear existing data (incompatible with new schema)
        migrations.RunSQL(
            sql='TRUNCATE TABLE "subscriptions" CASCADE;',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Change column type from UUID to VARCHAR
        migrations.RunSQL(
            sql='ALTER TABLE "subscriptions" ALTER COLUMN "user_id" TYPE VARCHAR(255) USING user_id::text;',
            reverse_sql='ALTER TABLE "subscriptions" ALTER COLUMN "user_id" TYPE UUID USING user_id::uuid;'
        ),
        
        # Recreate foreign key to clerk_user_id
        migrations.RunSQL(
            sql='ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users" ("clerk_user_id") DEFERRABLE INITIALLY DEFERRED;',
            reverse_sql='ALTER TABLE "subscriptions" DROP CONSTRAINT "subscriptions_user_id_fkey";'
        ),
    ]
