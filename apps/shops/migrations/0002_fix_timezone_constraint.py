# Generated manually to fix timezone column constraint

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Make timezone column nullable and set default to 'UTC'
            sql="ALTER TABLE shops ALTER COLUMN timezone DROP NOT NULL;",
            reverse_sql="ALTER TABLE shops ALTER COLUMN timezone SET NOT NULL;",
        ),
        migrations.RunSQL(
            # Set default value for timezone column
            sql="ALTER TABLE shops ALTER COLUMN timezone SET DEFAULT 'UTC';",
            reverse_sql="ALTER TABLE shops ALTER COLUMN timezone DROP DEFAULT;",
        ),
        migrations.RunSQL(
            # Update existing NULL values to 'UTC'
            sql="UPDATE shops SET timezone = 'UTC' WHERE timezone IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
