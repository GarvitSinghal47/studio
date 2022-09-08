# Generated by Django 3.2.14 on 2022-09-08 07:19
import uuid

import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations
from django.db import models

import contentcuration.models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('contentcuration', '0140_delete_task'),
        ('search', '0002_auto_20201215_2110'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContentNodeFullTextSearch',
            fields=[
                ('id', contentcuration.models.UUIDField(default=uuid.uuid4, max_length=32, primary_key=True, serialize=False)),
                ('keywords_tsvector', django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ('author_tsvector', django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='channel_nodes_fts', to='contentcuration.channel')),
                ('contentnode', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='node_fts', to='contentcuration.contentnode')),
            ],
        ),
        migrations.CreateModel(
            name='ChannelFullTextSearch',
            fields=[
                ('id', contentcuration.models.UUIDField(default=uuid.uuid4, max_length=32, primary_key=True, serialize=False)),
                ('keywords_tsvector', django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='channel_fts', to='contentcuration.channel')),
            ],
        ),
        AddIndexConcurrently(
            model_name='contentnodefulltextsearch',
            index=django.contrib.postgres.indexes.GinIndex(fields=['keywords_tsvector'], name='node_keywords_tsv__gin_idx'),
        ),
        AddIndexConcurrently(
            model_name='contentnodefulltextsearch',
            index=django.contrib.postgres.indexes.GinIndex(fields=['author_tsvector'], name='node_author_tsv__gin_idx'),
        ),
        AddIndexConcurrently(
            model_name='channelfulltextsearch',
            index=django.contrib.postgres.indexes.GinIndex(fields=['keywords_tsvector'], name='channel_keywords_tsv__gin_idx'),
        ),
    ]
