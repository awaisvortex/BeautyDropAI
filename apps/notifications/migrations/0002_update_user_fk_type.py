# Generated manually to fix User foreign key type mismatch

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("authentication", "0003_remove_user_avatar_url_remove_user_date_joined_and_more"),
    ]

    operations = [
        # Remove old foreign key constraint
        migrations.RunSQL(
            sql='ALTER TABLE "notifications" DROP CONSTRAINT IF EXISTS "notifications_user_id_fkey";',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Clear existing data (incompatible with new schema)
        migrations.RunSQL(
            sql='TRUNCATE TABLE "notifications" CASCADE;',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Change column type from UUID to VARCHAR
        migrations.RunSQL(
            sql='ALTER TABLE "notifications" ALTER COLUMN "user_id" TYPE VARCHAR(255) USING user_id::text;',
            reverse_sql='ALTER TABLE "notifications" ALTER COLUMN "user_id" TYPE UUID USING user_id::uuid;'
        ),
        
        # Recreate foreign key to clerk_user_id
        migrations.RunSQL(
            sql='ALTER TABLE "notifications" ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users" ("clerk_user_id") DEFERRABLE INITIALLY DEFERRED;',
            reverse_sql='ALTER TABLE "notifications" DROP CONSTRAINT "notifications_user_id_fkey";'
        ),
    ]
