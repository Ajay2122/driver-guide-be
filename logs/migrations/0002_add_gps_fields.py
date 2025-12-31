# Generated migration for GPS fields and LocationCache model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailylog',
            name='total_driving_distance',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Total miles driven (calculated from GPS coordinates)', max_digits=10),
        ),
        migrations.AddField(
            model_name='dailylog',
            name='route_stats',
            field=models.JSONField(blank=True, default=dict, help_text='Route statistics (segments, location counts, etc.)'),
        ),
        migrations.CreateModel(
            name='LocationCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location_name', models.CharField(db_index=True, help_text="Location name (e.g., 'Los Angeles Terminal')", max_length=500, unique=True)),
                ('latitude', models.DecimalField(decimal_places=7, help_text='Latitude coordinate', max_digits=10)),
                ('longitude', models.DecimalField(decimal_places=7, help_text='Longitude coordinate', max_digits=10)),
                ('formatted_address', models.TextField(blank=True, help_text='Full formatted address from geocoding service')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'location_cache',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='locationcache',
            index=models.Index(fields=['location_name'], name='logs_locati_locatio_idx'),
        ),
    ]

