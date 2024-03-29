# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Person.expires'
        db.add_column(u'person', 'expires',
                      self.gf('django.db.models.fields.DateField')(default=None, null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Person.expires'
        db.delete_column(u'person', 'expires')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'backend.am': {
            'Meta': {'object_name': 'AM', 'db_table': "u'am'"},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_am': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_am_ctte': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_dam': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_fd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'person': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "u'am'", 'unique': 'True', 'to': u"orm['backend.Person']"}),
            'slots': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        u'backend.log': {
            'Meta': {'object_name': 'Log', 'db_table': "u'log'"},
            'changed_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'log_written'", 'null': 'True', 'to': u"orm['backend.Person']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'logdate': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'logtext': ('backend.models.TextNullField', [], {'null': 'True', 'blank': 'True'}),
            'process': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'log'", 'to': u"orm['backend.Process']"}),
            'progress': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'backend.person': {
            'Meta': {'object_name': 'Person', 'db_table': "u'person'"},
            'bio': ('backend.models.TextNullField', [], {'null': 'True', 'blank': 'True'}),
            'cn': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            'expires': ('django.db.models.fields.DateField', [], {'default': 'None', 'null': 'True'}),
            'fd_comment': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'fpr': ('backend.models.FingerprintField', [], {'max_length': '40', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mn': ('django.db.models.fields.CharField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'sn': ('django.db.models.fields.CharField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'status_changed': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'uid': ('backend.models.CharNullField', [], {'max_length': '32', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.User']", 'unique': 'True', 'null': 'True'})
        },
        u'backend.process': {
            'Meta': {'object_name': 'Process', 'db_table': "u'process'"},
            'advocates': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'advocated'", 'blank': 'True', 'to': u"orm['backend.Person']"}),
            'applying_as': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'applying_for': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'archive_key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "u'processed'", 'null': 'True', 'to': u"orm['backend.AM']"}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'processes'", 'to': u"orm['backend.Person']"}),
            'progress': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['backend']