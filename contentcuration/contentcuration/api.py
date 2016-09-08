"""
This module acts as the only interface point between other apps and the database backend for the content.
It exposes several convenience functions for accessing content
"""
import logging
import os
from functools import wraps
from django.core.files import File as DjFile
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.http import HttpResponse
from kolibri.content import models as KolibriContent
from kolibri.content.utils import validate
from django.db import transaction
import models

def recurse(node, level=0):
    print ('\t' * level), node.id, node.lft, node.rght, node.title
    for child in ContentNode.objects.filter(parent=node).order_by('sort_order'):
        recurse(child, level + 1)

def clean_db():
    print "*********** CLEANING DATABASE ***********"
    for file_obj in models.File.objects.filter(Q(preset = None) | Q(contentnode=None)):
        print "Deletng unreferenced file", file_obj
        file_obj.delete()
    for node_obj in models.ContentNode.objects.filter(Q(parent=None) & Q(channel_main=None) & Q(channel_trash=None) & Q(user_clipboard=None)):
        print "Deletng unreferenced node", node_obj.pk
        node_obj.delete()
    for tag_obj in models.ContentTag.objects.filter(tagged_content=None):
        print "Deleting unreferenced tag", tag_obj.tag_name
        tag_obj.delete()
    print "*********** DONE ***********"

def calculate_node_metadata(node):
    metadata = {
        "total_count" : node.children.count(),
        "resource_count" : 0,
        "max_sort_order" : 1,
        "resource_size" : 0,
        "has_changed_descendant" : node.changed
    }

    if node.kind_id == "topic":
        for n in node.children.all():
            metadata['max_sort_order'] = max(n.sort_order, metadata['max_sort_order'])
            child_metadata = calculate_node_metadata(n)
            metadata['total_count'] += child_metadata['total_count']
            metadata['resource_size'] += child_metadata['resource_size']
            metadata['resource_count'] += child_metadata['resource_count']
            if child_metadata['has_changed_descendant']:
                metadata['has_changed_descendant'] = True

    else:
        metadata['resource_count'] = 1
        for f in node.files.all():
            metadata['resource_size'] += f.file_size
        metadata['max_sort_order'] = node.sort_order
    return metadata

def count_files(node):
    if node.kind_id == "topic":
        count = 0
        for n in node.children.all():
            count += count_files(n)
        return count
    return 1

    # For some reason, this returns sibling desendants too
    # return node.get_descendants(include_self=False).exclude(kind_id="topic").count()

def count_all_children(node):
    count = node.children.count()
    for n in node.children.all():
        count += count_all_children(n)
    return count

def get_total_size(node):
    total_size = 0
    if node.kind_id == "topic":
        for n in node.children.all():
            total_size += get_total_size(n)
    else:
        for f in node.files.all():
            total_size += f.file_size
    return total_size

def get_node_siblings(node):
    siblings = []
    for n in node.get_siblings(include_self=False):
        siblings.append(n.title)
    return siblings

def get_node_ancestors(node):
    ancestors = []
    for n in node.get_ancestors():
        ancestors.append(n.id)
    return ancestors

def get_child_names(node):
    names = []
    for n in node.get_children():
        names.append({"title": n.title, "id" : n.id})
    return names

def batch_add_tags(request):
    # check existing tag and subtract them from bulk_create
    insert_list = []
    tag_names = request.POST.getlist('tags[]')
    existing_tags = models.ContentTag.objects.filter(tag_name__in=tag_names)
    existing_tag_names = existing_tags.values_list('tag_name', flat=True)
    new_tag_names = set(tag_names) - set(existing_tag_names)
    for name in new_tag_names:
        insert_list.append(models.ContentTag(tag_name=name))
    new_tags = models.ContentTag.objects.bulk_create(insert_list)

    # bulk add all tags to selected nodes
    all_tags = set(existing_tags).union(set(new_tags))
    ThroughModel = models.Node.tags.through
    bulk_list = []
    node_pks = request.POST.getlist('nodes[]')
    for tag in all_tags:
        for pk in node_pks:
            bulk_list.append(ThroughModel(node_id=pk, contenttag_id=tag.pk))
    ThroughModel.objects.bulk_create(bulk_list)

    return HttpResponse("Tags are successfully saved.", status=200)

def get_file_diff(file_list):
    in_db_list = models.File.objects.annotate(filename=Concat('checksum', Value('.'),  'file_format')).filter(filename__in=file_list).values_list('filename', flat=True)
    to_return = list(set(file_list) - set(in_db_list))
    return to_return

def api_file_create(file_object, filename, source_url):
    hashed_name = os.path.splitext(file_object._name)[1].split(".")
    ext = hashed_name[-1]
    created = models.File.objects.filter(checksum=hashed_name[-2]).exists()
    size = file_object._size
    file_format = models.FileFormat.objects.get(extension=ext)
    file_obj = models.File(file_on_disk=file_object, file_format=file_format, original_filename=filename, file_size=size, source_url=source_url)
    file_obj.save()

    return {
        'hash' : file_obj.checksum + '.' + ext,
        'file_id': file_obj.pk,
        'created':created
    }

""" CHANNEL CREATE FUNCTIONS """
def api_create_channel(channel_data, content_data):
        channel = create_channel(channel_data) # Set up initial channel
        root_node = init_staging_tree(channel) # Set up initial staging tree
        # Fill in foreign key relationships (kinds, files (by checksum and contentnode=none), license)
        nodes = convert_data_to_nodes(content_data, root_node) # converts dict to django models
        # with atomic():
        #     commit_staging_tree(channel, nodes)# Set channel's main tree to be staging tree
        #     update_channel_metadata()
        return channel # Return new channel

def create_channel(channel_data):
    name = channel_data['name']
    description = channel_data['description']
    thumbnail = channel_data['thumbnail']
    return models.Channel.objects.create(name=name, description=description, thumbnail=thumbnail)

def init_staging_tree(channel):
    channel.staging_tree = models.ContentNode.objects.create(title=channel.name + " staging", kind_id="topic", sort_order=0)
    channel.staging_tree.save()
    channel.save()
    return channel.staging_tree

def convert_data_to_nodes(content_data, parent_node):
    for node_data in content_data:
        new_node = create_node(node_data, parent_node)
        convert_data_to_nodes(node_data['children'], new_node)

def create_node(node_data, parent_node):
    title=node_data['title']
    description=node_data['description']
    node_id=node_data['id']
    author = node_data['author']
    file_obj = models.File.objects.filter(checksum=node_data['file'].split('.')[0], contentnode=None).first()
    license = models.License.objects.get(license_name=license)
    print title
    return "title"
    # preset =
    # kind = preset.kind

    # models.ContentNode.objects.create(title=channel.name + " staging", kind_id="topic", sort_order=0)