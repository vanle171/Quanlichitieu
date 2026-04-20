from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('master_admin', '0013_remove_event_child_event_target_count_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='so_luong_su_kien_con',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='event',
            name='parent_event',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='child_events', to='master_admin.event'),
        ),
    ]
