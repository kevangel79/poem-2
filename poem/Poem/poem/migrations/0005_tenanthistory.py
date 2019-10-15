# Generated by Django 2.2.5 on 2019-10-15 11:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('poem', '0004_delete_metrics'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.CharField(max_length=191)),
                ('serialized_data', models.TextField()),
                ('object_repr', models.TextField()),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('comment', models.TextField(blank=True)),
                ('user', models.CharField(max_length=32)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
            ],
        ),
    ]
