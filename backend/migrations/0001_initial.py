# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Person'
        db.create_table('person', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auth.User'], unique=True, null=True)),
            ('cn', self.gf('django.db.models.fields.CharField')(max_length=250)),
            ('mn', self.gf('django.db.models.fields.CharField')(max_length=250, null=True, blank=True)),
            ('sn', self.gf('django.db.models.fields.CharField')(max_length=250, null=True, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(unique=True, max_length=75)),
            ('uid', self.gf('backend.models.CharNullField')(max_length=32, unique=True, null=True, blank=True)),
            ('fpr', self.gf('backend.models.CharNullField')(max_length=80, unique=True, null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('status_changed', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow)),
            ('fd_comment', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, null=True)),
        ))
        db.send_create_signal(u'backend', ['Person'])

        # Adding model 'AM'
        db.create_table('am', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('person', self.gf('django.db.models.fields.related.OneToOneField')(related_name='am', unique=True, to=orm['backend.Person'])),
            ('slots', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('is_am', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('is_fd', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_dam', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_am_ctte', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, null=True)),
        ))
        db.send_create_signal(u'backend', ['AM'])

        # Adding model 'Process'
        db.create_table('process', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('person', self.gf('django.db.models.fields.related.ForeignKey')(related_name='processes', to=orm['backend.Person'])),
            ('applying_as', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('applying_for', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('progress', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('manager', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='processed', null=True, to=orm['backend.AM'])),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('archive_key', self.gf('django.db.models.fields.CharField')(unique=True, max_length=128)),
        ))
        db.send_create_signal(u'backend', ['Process'])

        # Adding M2M table for field advocates on 'Process'
        db.create_table('process_advocates', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('process', models.ForeignKey(orm[u'backend.process'], null=False)),
            ('person', models.ForeignKey(orm[u'backend.person'], null=False))
        ))
        db.create_unique('process_advocates', ['process_id', 'person_id'])

        # Adding model 'Log'
        db.create_table('log', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changed_by', self.gf('django.db.models.fields.related.ForeignKey')(related_name='log_written', null=True, to=orm['backend.Person'])),
            ('process', self.gf('django.db.models.fields.related.ForeignKey')(related_name='log', to=orm['backend.Process'])),
            ('progress', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('logdate', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow)),
            ('logtext', self.gf('backend.models.TextNullField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'backend', ['Log'])


    def backwards(self, orm):
        # Deleting model 'Person'
        db.delete_table('person')

        # Deleting model 'AM'
        db.delete_table('am')

        # Deleting model 'Process'
        db.delete_table('process')

        # Removing M2M table for field advocates on 'Process'
        db.delete_table('process_advocates')

        # Deleting model 'Log'
        db.delete_table('log')


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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'backend.am': {
            'Meta': {'object_name': 'AM', 'db_table': "'am'"},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_am': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_am_ctte': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_dam': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_fd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'person': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'am'", 'unique': 'True', 'to': u"orm['backend.Person']"}),
            'slots': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        u'backend.log': {
            'Meta': {'object_name': 'Log', 'db_table': "'log'"},
            'changed_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'log_written'", 'null': 'True', 'to': u"orm['backend.Person']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logdate': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'logtext': ('backend.models.TextNullField', [], {'null': 'True', 'blank': 'True'}),
            'process': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'log'", 'to': u"orm['backend.Process']"}),
            'progress': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'backend.person': {
            'Meta': {'object_name': 'Person', 'db_table': "'person'"},
            'cn': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            'fd_comment': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'fpr': ('backend.models.CharNullField', [], {'max_length': '80', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mn': ('django.db.models.fields.CharField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'sn': ('django.db.models.fields.CharField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'status_changed': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'uid': ('backend.models.CharNullField', [], {'max_length': '32', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.User']", 'unique': 'True', 'null': 'True'})
        },
        u'backend.process': {
            'Meta': {'object_name': 'Process', 'db_table': "'process'"},
            'advocates': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'advocated'", 'blank': 'True', 'to': u"orm['backend.Person']"}),
            'applying_as': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'applying_for': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'archive_key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'processed'", 'null': 'True', 'to': u"orm['backend.AM']"}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'processes'", 'to': u"orm['backend.Person']"}),
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