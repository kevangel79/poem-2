from collections import OrderedDict
import datetime

from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.test.client import encode_multipart

import json

from Poem.api import views_internal as views
from Poem.api.internal_views.utils import sync_webapi
from Poem.api.internal_views.utils import inline_metric_for_db
from Poem.api.models import MyAPIKey
from Poem.helpers.history_helpers import create_comment, update_comment
from Poem.helpers.versioned_comments import new_comment
from Poem.poem import models as poem_models
from Poem.poem_super_admin import models as admin_models
from Poem.tenants.models import Tenant
from Poem.users.models import CustUser

from rest_framework.test import force_authenticate
from rest_framework import status

from tenant_schemas.test.cases import TenantTestCase
from tenant_schemas.test.client import TenantRequestFactory
from tenant_schemas.utils import schema_context, get_public_schema_name

from unittest.mock import patch


def encode_data(data):
    content = encode_multipart('BoUnDaRyStRiNg', data)
    content_type = 'multipart/form-data; boundary=BoUnDaRyStRiNg'

    return content, content_type


def mocked_func(*args):
    pass


def mocked_inline_metric_for_db(data):
    data = json.loads(data)

    result = []
    for item in data:
        if item['key']:
            result.append('{} {}'.format(item['key'], item['value']))

    if result:
        return json.dumps(result)
    else:
        return ''


def mocked_web_api_request(*args, **kwargs):
    class MockResponse:
        def __init__(self, data, status_code):
            self.data = data
            self.status_code = status_code

        def json(self):
            return self.data

        def raise_for_status(self):
            return ''

    if args[0] == 'metric_profiles':
        return MockResponse(
            {
                'data': [
                    {
                        'id': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'date': '2015-01-01',
                        'name': 'TEST_PROFILE',
                        'services': [
                            {
                                'service': 'dg.3GBridge',
                                'metrics': [
                                    'eu.egi.cloud.Swift-CRUD'
                                ]
                            }
                        ]
                    },
                    {
                        'id': '11110000-aaaa-kkkk-aaaa-aaeekkccnnee',
                        'date': '2015-01-01',
                        'name': 'NEW_PROFILE',
                        'services': [
                            {
                                'service': 'dg.3GBridge',
                                'metrics': [
                                    'eu.egi.cloud.Swift-CRUD'
                                ]
                            }
                        ]

                    }
                ]
            }, 200
        )

    if args[0] == 'aggregation_profiles':
        return MockResponse(
            {
                'data': [
                    {
                        'id': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'date': '2015-01-01',
                        'name': 'TEST_PROFILE',
                        'namespace': 'egi',
                        'endpoint_group': 'sites',
                        'metric_operation': 'AND',
                        'profile_operation': 'AND',
                        'metric_profile': {
                            'name': 'TEST_PROFILE',
                            'id': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        },
                        'groups': []
                    },
                    {
                        'id': '11110000-aaaa-kkkk-aaaa-aaeekkccnnee',
                        'date': '2015-01-01',
                        'name': 'NEW_PROFILE',
                        'namespace': 'egi',
                        'endpoint_group': 'sites',
                        'metric_operation': 'AND',
                        'profile_operation': 'AND',
                        'metric_profile': {
                            'name': 'TEST_PROFILE',
                            'id': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        },
                        'groups': []

                    }
                ]
            }, 200
        )

    if args[0] == 'thresholds_profiles':
        return MockResponse(
            {
                'data': [
                    {
                        'id': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'date': '2015-01-01',
                        'name': 'TEST_PROFILE',
                        'rules': [
                            {
                                'metric': 'httpd.ResponseTime',
                                'thresholds': 'response=20ms;0:300;299:1000'
                            },
                            {
                                'host': 'webserver01.example.foo',
                                'metric': 'httpd.ResponseTime',
                                'thresholds': 'response=20ms;0:200;199:300'
                            },
                            {
                                'endpoint_group': 'TEST-SITE-51',
                                'metric': 'httpd.ResponseTime',
                                'thresholds': 'response=20ms;0:500;499:1000'
                            }
                        ]
                    },
                    {
                        'id': '11110000-aaaa-kkkk-aaaa-aaeekkccnnee',
                        'date': '2015-01-01',
                        'name': 'NEW_PROFILE',
                        'rules': [
                            {
                                'metric': 'httpd.ResponseTime',
                                'thresholds': 'response=20ms;0:300;299:1000'
                            }
                        ]
                    }
                ]
            }, 200
        )


class ListAPIKeysAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListAPIKeys.as_view()
        self.url = '/api/v2/internal/apikeys/'
        self.user = CustUser.objects.create_user(
            username='testuser', is_superuser=True
        )

        key1, k1 = MyAPIKey.objects.create_key(name='EGI')
        self.id1 = key1.id
        self.token1 = key1.token
        self.created1 = datetime.datetime.strftime(key1.created,
                                                   '%Y-%m-%d %H:%M:%S')
        key2, k2 = MyAPIKey.objects.create_key(name='EUDAT')
        self.id2 = key2.id
        self.token2 = key2.token
        self.created2 = datetime.datetime.strftime(key2.created,
                                                   '%Y-%m-%d %H:%M:%S')
        key3, k3 = MyAPIKey.objects.create_key(name='DELETABLE')
        self.id3 = key3.id
        self.token3 = key3.token
        self.created3 = datetime.datetime.strftime(key3.created,
                                                   '%Y-%m-%d %H:%M:%S')

    def test_permission_denied_in_case_no_authorization(self):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_list_of_apikeys(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.id3,
                    'name': 'DELETABLE',
                    'token': self.token3,
                    'created': self.created3,
                    'revoked': False
                },
                {
                    'id': self.id1,
                    'name': 'EGI',
                    'token': self.token1,
                    'created': self.created1,
                    'revoked': False
                },
                {
                    'id': self.id2,
                    'name': 'EUDAT',
                    'token': self.token2,
                    'created': self.created2,
                    'revoked': False
                }
            ]
        )

    def test_get_apikey_for_given_name(self):
        request = self.factory.get(self.url + 'EGI')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'EGI')
        self.assertEqual(
            response.data,
            {
                'id': self.id1,
                'name': 'EGI',
                'token': self.token1,
                'created': self.created1,
                'revoked': False
            }
        )

    def test_put_apikey(self):
        data = {'id': self.id1, 'name': 'EGI2', 'revoked': False}
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        changed_entry = MyAPIKey.objects.get(id=self.id1)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual('EGI2', changed_entry.name)

    def test_put_apikey_with_name_that_already_exists(self):
        data = {'id': self.id1, 'name': 'EUDAT', 'revoked': False}
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_apikey(self):
        data = {'name': 'test', 'revoked': False}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_post_apikey_name_already_exists(self):
        data = {'name': 'EUDAT', 'revoked': False}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_apikey(self):
        request = self.factory.delete(self.url + 'DELETABLE')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'DELETABLE')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_nonexisting_apikey(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_no_apikey_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListUsersAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListUsers.as_view()
        self.url = '/api/v2/internal/users/'
        self.user = CustUser.objects.create_user(
            username='testuser',
            first_name='Test',
            last_name='User',
            email='testuser@example.com',
            date_joined=datetime.datetime(2015, 1, 1, 0, 0, 0)
        )

        self.user2 = CustUser.objects.create_user(
            username='another_user',
            first_name='Another',
            last_name='User',
            email='otheruser@example.com',
            is_superuser=True,
            date_joined=datetime.datetime(2015, 1, 2, 0, 0, 0)
        )

        poem_models.UserProfile.objects.create(user=self.user2)

        self.groupofmetrics = poem_models.GroupOfMetrics.objects.create(
            name='Metric1'
        )
        self.groupofmetricprofiles = \
            poem_models.GroupOfMetricProfiles.objects.create(name='MP1')
        self.groupofaggregations = \
            poem_models.GroupOfAggregations.objects.create(name='Aggr1')

    def test_get_users(self):
        self.maxDiff = None
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user2)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                OrderedDict([('first_name', 'Another'),
                             ('last_name', 'User'),
                             ('username', 'another_user'),
                             ('is_active', True),
                             ('is_superuser', True),
                             ('email', 'otheruser@example.com'),
                             ('date_joined', '2015-01-02T00:00:00'),
                             ('pk', self.user2.pk)]),
                OrderedDict([('first_name', 'Test'),
                             ('last_name', 'User'),
                             ('username', 'testuser'),
                             ('is_active', True),
                             ('is_superuser', False),
                             ('email', 'testuser@example.com'),
                             ('date_joined', '2015-01-01T00:00:00'),
                             ('pk', self.user.pk)])
            ]
        )

    def test_get_users_permission_denied_in_case_no_authorization(self):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_user_by_username(self):
        request = self.factory.get(self.url + 'testuser')
        force_authenticate(request, user=self.user2)
        response = self.view(request, 'testuser')
        self.assertEqual(
            response.data,
            OrderedDict([('first_name', 'Test'),
                         ('last_name', 'User'),
                         ('username', 'testuser'),
                         ('is_active', True),
                         ('is_superuser', False),
                         ('email', 'testuser@example.com'),
                         ('date_joined', '2015-01-01T00:00:00'),
                         ('pk', self.user.pk)])
        )

    def test_get_user_by_username_if_username_does_not_exist(self):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_user(self):
        data = {
            'pk': self.user.pk,
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'Newuser',
            'email': 'testuser@example.com',
            'is_superuser': False,
            'is_active': True
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user2)
        response = self.view(request)
        user = CustUser.objects.get(username='testuser')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'Newuser')
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_put_user_with_already_existing_name(self):
        data = {
            'pk': self.user.pk,
            'username': 'another_user',
            'first_name': 'Test',
            'last_name': 'Newuser',
            'email': 'testuser@example.com',
            'is_superuser': False,
            'is_active': True
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user2)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'User with this username already exists.'}
        )

    def test_post_user(self):
        data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'is_superuser': True,
            'is_active': True,
            'password': 'blablabla',
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user2)
        response = self.view(request)
        user = CustUser.objects.get(username='newuser')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_post_user_with_already_existing_username(self):
        data = {
            'username': 'testuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'is_superuser': True,
            'is_active': True,
            'password': 'blablabla',
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user2)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'User with this username already exists.'}
        )

    def test_delete_user(self):
        request = self.factory.delete(self.url + 'another_user')
        force_authenticate(request, user=self.user2)
        response = self.view(request, 'another_user')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_nonexisting_user(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user2)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_user_without_specifying_username(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user2)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListProbesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListProbes.as_view()
        self.url = '/api/v2/internal/probes/'
        self.user = CustUser.objects.create_user(username='testuser')

        with schema_context(get_public_schema_name()):
            Tenant.objects.create(name='public', domain_url='public',
                                  schema_name=get_public_schema_name())

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(
            name='repo-1', tag=tag
        )

        self.package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        self.package1.repos.add(repo)

        self.package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        self.package2.repos.add(repo)

        self.probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=self.package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user='testuser',
            datetime=datetime.datetime.now()
        )

        self.probe2 = admin_models.Probe.objects.create(
            name='argo-web-api',
            package=self.package1,
            description='This is a probe for checking AR and status reports are'
                        ' properly working.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        probe3 = admin_models.Probe.objects.create(
            name='ams-publisher-probe',
            package=self.package2,
            description='Probe is inspecting AMS publisher running on Nagios '
                        'monitoring instances.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user='testuser',
            datetime=datetime.datetime.now()
        )

        pv1 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        pv = admin_models.ProbeHistory.objects.create(
            object_id=self.probe2,
            name=self.probe2.name,
            package=self.probe2.package,
            description=self.probe2.description,
            comment=self.probe2.comment,
            repository=self.probe2.repository,
            docurl=self.probe2.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.probe1.package = self.package2
        self.probe1.comment = 'Newer version.'
        self.probe1.save()

        pv2 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            version_comment='[{"changed": {"fields": ["package", "comment"]}}]',
            version_user=self.user.username
        )

        admin_models.ProbeHistory.objects.create(
            object_id=probe3,
            name=probe3.name,
            package=probe3.package,
            description=probe3.description,
            comment=probe3.comment,
            repository=probe3.repository,
            docurl=probe3.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        mtype = admin_models.MetricTemplateType.objects.create(name='Active')
        metrictype = poem_models.MetricType.objects.create(name='Active')

        group = poem_models.GroupOfMetrics.objects.create(name='TEST')

        ct = ContentType.objects.get_for_model(poem_models.Metric)

        admin_models.MetricTemplate.objects.create(
            name='argo.API-Check',
            mtype=mtype,
            probekey=pv,
            probeexecutable='["web-api"]',
            config='["maxCheckAttempts 3", "timeout 120", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.api_TOKEN --token"]',
            flags='["OBSESS 1"]'
        )

        admin_models.MetricTemplate.objects.create(
            name='argo.AMS-Check',
            mtype=mtype,
            probekey=pv2,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        metric1 = poem_models.Metric.objects.create(
            name='argo.API-Check',
            mtype=metrictype,
            group=group,
            probekey=pv,
            probeexecutable='["web-api"]',
            config='["maxCheckAttempts 3", "timeout 120", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.api_TOKEN --token"]',
            flags='["OBSESS 1"]'
        )

        metric2 = poem_models.Metric.objects.create(
            name='argo.AMS-Check',
            group=group,
            mtype=metrictype,
            probekey=pv2,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        poem_models.TenantHistory.objects.create(
            object_id=metric1.id,
            serialized_data=serializers.serialize(
                'json', [metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=metric1.__str__(),
            content_type=ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        poem_models.TenantHistory.objects.create(
            object_id=metric2.id,
            serialized_data=serializers.serialize(
                'json', [metric2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=metric2.__str__(),
            content_type=ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

    def test_get_list_of_all_probes(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'name': 'ams-probe',
                    'version': '0.1.11',
                    'package': 'nagios-plugins-argo (0.1.11)',
                    'docurl':
                        'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
                        'master/README.md',
                    'description': 'Probe is inspecting AMS service by trying '
                                   'to publish and consume randomly generated '
                                   'messages.',
                    'comment': 'Newer version.',
                    'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo',
                    'nv': 2
                },
                {
                    'name': 'ams-publisher-probe',
                    'version': '0.1.11',
                    'package': 'nagios-plugins-argo (0.1.11)',
                    'docurl':
                        'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
                        'master/README.md',
                    'description': 'Probe is inspecting AMS publisher running '
                                   'on Nagios monitoring instances.',
                    'comment': 'Initial version.',
                    'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo',
                    'nv': 1
                },
                {
                    'name': 'argo-web-api',
                    'version': '0.1.7',
                    'package': 'nagios-plugins-argo (0.1.7)',
                    'description': 'This is a probe for checking AR and status '
                                   'reports are properly working.',
                    'comment': 'Initial version.',
                    'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo',
                    'docurl': 'https://github.com/ARGOeu/nagios-plugins-argo/'
                              'blob/master/README.md',
                    'nv': 1
                }
            ]
        )

    def test_get_probe_by_name(self):
        request = self.factory.get(self.url + 'ams-probe')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'ams-probe')
        self.assertEqual(
            response.data,
            {
                'id': self.probe1.id,
                'name': 'ams-probe',
                'version': '0.1.11',
                'package': 'nagios-plugins-argo (0.1.11)',
                'docurl':
                    'https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                    'README.md',
                'description': 'Probe is inspecting AMS service by trying to '
                               'publish and consume randomly generated '
                               'messages.',
                'comment': 'Newer version.',
                'repository': 'https://github.com/ARGOeu/nagios-plugins-argo',
                'user': 'testuser',
                'datetime': datetime.datetime.strftime(
                    self.probe1.datetime,
                    '%Y-%m-%dT%H:%M:%S.%f'
                ),
            }
        )

    def test_get_probe_by_name_if_no_datetime_nor_user(self):
        request = self.factory.get(self.url + 'argo-web-api')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'argo-web-api')
        self.assertEqual(
            response.data,
            {
                'id': self.probe2.id,
                'name': 'argo-web-api',
                'version': '0.1.7',
                'package': 'nagios-plugins-argo (0.1.7)',
                'docurl':
                    'https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                    'README.md',
                'description': 'This is a probe for checking AR and status '
                               'reports are properly working.',
                'comment': 'Initial version.',
                'repository': 'https://github.com/ARGOeu/nagios-plugins-argo',
                'user': '',
                'datetime': ''
            }
        )

    def test_get_probe_permission_denied_in_case_of_no_authorization(self):
        request = self.factory.get(self.url + 'ams-probe')
        response = self.view(request, 'ams-probe')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_probe_empty_dict_in_case_of_nonexisting_probe(self):
        request = self.factory.get(self.url + 'nonexisting_probe')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting_probe')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_probe_with_already_existing_name(self):
        data = {
            'id': self.probe1.id,
            'name': 'argo-web-api',
            'package': 'nagios-plugins-argo (0.1.7)',
            'comment': 'New version.',
            'docurl':
                'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
                'master/README.md',
            'description': 'Probe is inspecting AMS service by trying '
                           'to publish and consume randomly generated '
                           'messages.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                          'argo',
            'update_metrics': False
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Probe with this name already exists.'}
        )

    def test_put_probe_without_new_version(self):
        data = {
            'id': self.probe1.id,
            'name': 'ams-probe-new',
            'package': 'nagios-plugins-argo (0.1.11)',
            'comment': 'Newer version.',
            'docurl':
                'https://github.com/ARGOeu/nagios-plugins-argo2/blob/'
                'master/README.md',
            'description': 'Probe is inspecting AMS service.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                          'argo2',
            'update_metrics': False
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        probe = admin_models.Probe.objects.get(id=self.probe1.id)
        version = admin_models.ProbeHistory.objects.get(
            name=probe.name, package__version=probe.package.version
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(probe.name, 'ams-probe-new')
        self.assertEqual(probe.package, self.package2)
        self.assertEqual(probe.comment, 'Newer version.')
        self.assertEqual(
            probe.docurl,
            'https://github.com/ARGOeu/nagios-plugins-argo2/blob/master/'
            'README.md',
        )
        self.assertEqual(
            probe.description,
            'Probe is inspecting AMS service.'
        )
        self.assertEqual(
            probe.repository,
            'https://github.com/ARGOeu/nagios-plugins-argo2',
        )
        self.assertEqual(version.name, probe.name)
        self.assertEqual(version.package, probe.package)
        self.assertEqual(version.comment, probe.comment)
        self.assertEqual(version.docurl, probe.docurl)
        self.assertEqual(version.description, probe.description)
        self.assertEqual(version.repository, probe.repository)
        self.assertEqual(
            version.version_comment,
            '[{"changed": {"fields": ["comment", "description", "docurl", '
            '"name", "package", "repository"]}}]'
        )
        mt = admin_models.MetricTemplate.objects.get(name='argo.AMS-Check')
        self.assertEqual(mt.probekey, version)
        metric = poem_models.Metric.objects.get(name='argo.AMS-Check')
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["ams-probe"]')
        self.assertEqual(metric.probekey, version)
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 3", "timeout 60", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 5", "retryInterval 3"]'
        )
        self.assertEqual(metric.attribute, '["argo.ams_TOKEN --token"]')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '["--project EGI"]')
        self.assertEqual(metric.fileparameter, '')
        mt_history = poem_models.TenantHistory.objects.filter(
            object_repr='argo.AMS-Check'
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(
            mt_history[0].comment, 'Initial version.'
        )
        serialized_data = json.loads(mt_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], ['Active'])
        self.assertEqual(
            serialized_data['probekey'], ['ams-probe-new', '0.1.11']
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    def test_put_probe_no_new_name_metric_history_without_new_version(self):
        data = {
            'id': self.probe1.id,
            'name': 'ams-probe',
            'package': 'nagios-plugins-argo (0.1.11)',
            'comment': 'Newer version.',
            'docurl':
                'https://github.com/ARGOeu/nagios-plugins-argo2/blob/'
                'master/README.md',
            'description': 'Probe is inspecting AMS service.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                          'argo2',
            'update_metrics': False
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        probe = admin_models.Probe.objects.get(id=self.probe1.id)
        version = admin_models.ProbeHistory.objects.get(
            name=probe.name, package__version=probe.package.version
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(probe.name, 'ams-probe')
        self.assertEqual(probe.package, self.package2)
        self.assertEqual(probe.comment, 'Newer version.')
        self.assertEqual(
            probe.docurl,
            'https://github.com/ARGOeu/nagios-plugins-argo2/blob/master/'
            'README.md',
        )
        self.assertEqual(
            probe.description,
            'Probe is inspecting AMS service.'
        )
        self.assertEqual(
            probe.repository,
            'https://github.com/ARGOeu/nagios-plugins-argo2',
        )
        self.assertEqual(version.name, probe.name)
        self.assertEqual(version.package, probe.package)
        self.assertEqual(version.comment, probe.comment)
        self.assertEqual(version.docurl, probe.docurl)
        self.assertEqual(version.description, probe.description)
        self.assertEqual(version.repository, probe.repository)
        self.assertEqual(
            version.version_comment,
            '[{"changed": {"fields": ["comment", "description", "docurl", '
            '"package", "repository"]}}]'
        )
        mt = admin_models.MetricTemplate.objects.get(name='argo.AMS-Check')
        self.assertEqual(mt.probekey, version)
        metric = poem_models.Metric.objects.get(name='argo.AMS-Check')
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["ams-probe"]')
        self.assertEqual(metric.probekey, version)
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 3", "timeout 60", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 5", "retryInterval 3"]'
        )
        self.assertEqual(metric.attribute, '["argo.ams_TOKEN --token"]')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '["--project EGI"]')
        self.assertEqual(metric.fileparameter, '')
        mt_history = poem_models.TenantHistory.objects.filter(
            object_repr='argo.AMS-Check'
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(
            mt_history[0].comment, 'Initial version.'
        )
        serialized_data = json.loads(mt_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], ['Active'])
        self.assertEqual(
            serialized_data['probekey'], ['ams-probe', '0.1.11']
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    def test_put_probe_with_new_version_without_metrictemplate_update(self):
        data = {
            'id': self.probe2.id,
            'name': 'web-api',
            'package': 'nagios-plugins-argo (0.1.11)',
            'comment': 'New version.',
            'docurl':
                'https://github.com/ARGOeu/nagios-plugins-argo2/blob/'
                'master/README.md',
            'description': 'Probe is checking AR and status reports.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                          'argo2',
            'update_metrics': False
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        probe = admin_models.Probe.objects.get(id=self.probe2.id)
        self.assertEqual(
            admin_models.ProbeHistory.objects.filter(object_id=probe).count(), 2
        )
        version = admin_models.ProbeHistory.objects.get(
            name=probe.name, package__version=probe.package.version)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(probe.name, 'web-api')
        self.assertEqual(probe.package, self.package2)
        self.assertEqual(probe.comment, 'New version.')
        self.assertEqual(
            probe.docurl,
            'https://github.com/ARGOeu/nagios-plugins-argo2/blob/master/'
            'README.md',
        )
        self.assertEqual(
            probe.description,
            'Probe is checking AR and status reports.'
        )
        self.assertEqual(
            probe.repository,
            'https://github.com/ARGOeu/nagios-plugins-argo2',
        )
        self.assertEqual(version.name, probe.name)
        self.assertEqual(version.package, probe.package)
        self.assertEqual(version.comment, probe.comment)
        self.assertEqual(version.docurl, probe.docurl)
        self.assertEqual(version.description, probe.description)
        self.assertEqual(version.repository, probe.repository)
        self.assertEqual(
            version.version_comment,
            '[{"changed": {"fields": ["comment", "description", "docurl", '
            '"name", "package", "repository"]}}]'
        )
        mt = admin_models.MetricTemplate.objects.get(name='argo.API-Check')
        self.assertEqual(
            mt.probekey,
            admin_models.ProbeHistory.objects.filter(
                object_id=probe
            ).order_by('-date_created')[1]
        )
        metric = poem_models.Metric.objects.get(name='argo.API-Check')
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["web-api"]')
        self.assertEqual(
            metric.probekey,
            admin_models.ProbeHistory.objects.filter(object_id=probe)[1]
        )
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 3", "timeout 120", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 5", "retryInterval 3"]'
        )
        self.assertEqual(metric.attribute, '["argo.api_TOKEN --token"]')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '')
        self.assertEqual(metric.fileparameter, '')
        mt_history = poem_models.TenantHistory.objects.filter(
            object_repr='argo.API-Check'
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(
            mt_history[0].comment, 'Initial version.'
        )
        serialized_data = json.loads(mt_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], ['Active'])
        self.assertEqual(
            serialized_data['probekey'], ['argo-web-api', '0.1.7']
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    def test_put_probe_with_new_version_with_metrictemplate_update(self):
        data = {
            'id': self.probe2.id,
            'name': 'web-api',
            'package': 'nagios-plugins-argo (0.1.11)',
            'comment': 'New version.',
            'docurl':
                'https://github.com/ARGOeu/nagios-plugins-argo2/blob/'
                'master/README.md',
            'description': 'Probe is checking AR and status reports.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-'
                          'argo2',
            'update_metrics': True
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content,
                                   content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        probe = admin_models.Probe.objects.get(id=self.probe2.id)
        self.assertEqual(
            admin_models.ProbeHistory.objects.filter(object_id=probe).count(), 2
        )
        version = admin_models.ProbeHistory.objects.filter(
            object_id=self.probe2
        ).order_by('-date_created')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(probe.name, 'web-api')
        self.assertEqual(probe.package, self.package2)
        self.assertEqual(probe.comment, 'New version.')
        self.assertEqual(
            probe.docurl,
            'https://github.com/ARGOeu/nagios-plugins-argo2/blob/master/'
            'README.md',
        )
        self.assertEqual(
            probe.description,
            'Probe is checking AR and status reports.'
        )
        self.assertEqual(
            probe.repository,
            'https://github.com/ARGOeu/nagios-plugins-argo2',
        )
        self.assertEqual(version[0].name, probe.name)
        self.assertEqual(version[0].package, probe.package)
        self.assertEqual(version[0].comment, probe.comment)
        self.assertEqual(version[0].docurl, probe.docurl)
        self.assertEqual(version[0].description, probe.description)
        self.assertEqual(version[0].repository, probe.repository)
        mt = admin_models.MetricTemplate.objects.get(name='argo.API-Check')
        self.assertEqual(mt.probekey, version[0])
        metric = poem_models.Metric.objects.get(name='argo.API-Check')
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["web-api"]')
        self.assertEqual(metric.probekey, version[1])
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 3", "timeout 120", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 5", "retryInterval 3"]'
        )
        self.assertEqual(metric.attribute, '["argo.api_TOKEN --token"]')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '')
        self.assertEqual(metric.fileparameter, '')
        mt_history = poem_models.TenantHistory.objects.filter(
            object_repr='argo.API-Check'
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(
            mt_history[0].comment, 'Initial version.'
        )
        serialized_data = json.loads(mt_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], ['Active'])
        self.assertEqual(
            serialized_data['probekey'], ['argo-web-api', '0.1.7']
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    def test_post_probe(self):
        data = {
            'name': 'poem-probe',
            'package': 'nagios-plugins-argo (0.1.11)',
            'description': 'Probe inspects POEM service.',
            'comment': 'Initial version.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-argo',
            'docurl': 'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
                      'master/README.md',
            'user': 'testuser',
            'datetime': datetime.datetime.now(),
            'cloned_from': ''
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        probe = admin_models.Probe.objects.get(name='poem-probe')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(probe.package, self.package2)
        self.assertEqual(probe.description, 'Probe inspects POEM service.')
        self.assertEqual(probe.comment, 'Initial version.')
        self.assertEqual(probe.repository,
                         'https://github.com/ARGOeu/nagios-plugins-argo')
        self.assertEqual(
            probe.docurl,
            'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
            'master/README.md'
        )
        self.assertEqual(
            admin_models.ProbeHistory.objects.filter(object_id=probe).count(), 1
        )
        version = admin_models.ProbeHistory.objects.get(
            name=probe.name, package__version=probe.package.version
        )
        self.assertEqual(version.name, probe.name)
        self.assertEqual(version.package, probe.package)
        self.assertEqual(version.comment, probe.comment)
        self.assertEqual(version.docurl, probe.docurl)
        self.assertEqual(version.description, probe.description)
        self.assertEqual(version.repository, probe.repository)

    def test_post_cloned_probe(self):
        data = {
            'name': 'poem-probe',
            'package': 'nagios-plugins-argo (0.1.11)',
            'description': 'Probe inspects POEM service.',
            'comment': 'Initial version.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-argo',
            'docurl': 'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
                      'master/README.md',
            'user': 'testuser',
            'datetime': datetime.datetime.now(),
            'cloned_from': self.probe1.id
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        probe = admin_models.Probe.objects.get(name='poem-probe')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(probe.package, self.package2)
        self.assertEqual(probe.description, 'Probe inspects POEM service.')
        self.assertEqual(probe.comment, 'Initial version.')
        self.assertEqual(probe.repository,
                         'https://github.com/ARGOeu/nagios-plugins-argo')
        self.assertEqual(
            probe.docurl,
            'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
            'master/README.md'
        )
        self.assertEqual(
            admin_models.ProbeHistory.objects.filter(object_id=probe).count(), 1
        )
        version = admin_models.ProbeHistory.objects.get(
            name=probe.name, package__version=probe.package.version
        )
        self.assertEqual(version.name, probe.name)
        self.assertEqual(version.package, probe.package)
        self.assertEqual(version.comment, probe.comment)
        self.assertEqual(version.docurl, probe.docurl)
        self.assertEqual(version.description, probe.description)
        self.assertEqual(version.repository, probe.repository)
        self.assertEqual(
            version.version_comment, 'Derived from ams-probe (0.1.11).'
        )

    def test_post_probe_with_name_which_already_exists(self):
        data = {
            'name': 'ams-probe',
            'package': 'nagios-plugins-argo (0.1.11)',
            'description': 'Probe inspects POEM service.',
            'comment': 'Initial version.',
            'repository': 'https://github.com/ARGOeu/nagios-plugins-argo',
            'docurl': 'https://github.com/ARGOeu/nagios-plugins-argo/blob/'
                      'master/README.md',
            'user': 'testuser',
            'datetime': datetime.datetime.now()
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                'detail': 'Probe with this name already exists.'
            }
        )

    def test_delete_probe(self):
        self.assertEqual(admin_models.Probe.objects.all().count(), 3)
        request = self.factory.delete(self.url + 'ams-publisher-probe')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'ams-publisher-probe')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(admin_models.Probe.objects.all().count(), 2)

    def test_delete_probe_associated_to_metric_template(self):
        request = self.factory.delete(self.url + 'argo-web-api')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'argo-web-api')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                'detail': 'You cannot delete Probe that is associated to metric'
                          ' templates!'
            }
        )

    def test_delete_probe_without_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trying_to_delete_nonexisting_probe(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Probe not found'})


class ListServicesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListServices.as_view()
        self.url = '/api/v2/internal/services/'
        self.user = CustUser.objects.create(username='testuser')

        poem_models.Service.objects.create(
            id='2838b1ae-af25-4719-89c5-5484181d6201',
            service_id='7dc97be9-bcd9-46af-8bca-aa976bc8e207',
            service_name='B2SAFE',
            service_category='Storage & Data',
            service_version='1',
            service_type='b2safe.dsi',
            component_version='1.11.13',
            component_name='Storage',
            visible_to_marketplace=False,
            in_catalogue=True,
            external_service=False,
            internal_service=False
        )

        poem_models.Service.objects.create(
            id='31024d6a-9dd4-44d9-996e-599108ed23a7',
            service_id='39917801-850e-4378-9ca3-ea2d2bfc5860',
            service_name='EGI DataHub',
            service_category='Storage & Data',
            service_version='1',
            service_type='org.onedata.oneprovider',
            component_version='stable',
            component_name='OpenData',
            visible_to_marketplace=False,
            in_catalogue=True,
            external_service=False,
            internal_service=False
        )

        poem_models.Service.objects.create(
            id='4d297cea-5bf7-434a-b428-b52d35dfcac1',
            service_id='9689afb1-f5d6-4716-ae5e-9de347803884',
            service_name='EGI Online Storage',
            service_category='Storage & Data',
            service_version='1',
            service_type='SRM',
            component_version='1.11.13',
            component_name='Storage',
            visible_to_marketplace=False,
            in_catalogue=True,
            external_service=False,
            internal_service=False
        )

        poem_models.ServiceFlavour.objects.create(
            name='org.onedata.oneprovider',
            description='Oneprovider is a Onedata component...'
        )

        poem_models.ServiceFlavour.objects.create(
            name='SRM',
            description='Storage Resource Manager.'
        )

        poem_models.MetricInstance.objects.create(
            service_flavour='org.onedata.oneprovider',
            metric='org.onedata.Oneprovider-Health'
        )

        poem_models.MetricInstance.objects.create(
            service_flavour='org.onedata.oneprovider',
            metric='eu.egi.CertValidity'
        )

        poem_models.MetricInstance.objects.create(
            service_flavour='SRM',
            metric='hr.srce.SRM2-CertLifetime'
        )

        poem_models.MetricInstance.objects.create(
            service_flavour='SRM',
            metric='org.sam.SRM-All'
        )

        mtype = poem_models.MetricType.objects.create(
            name='Active'
        )

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(
            name='repo-1', tag=tag
        )

        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-onedata',
            version='3.2.0'
        )
        package1.repos.add(repo)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-check_ssl_cert',
            version='1.84.0'
        )
        package2.repos.add(repo)

        package3 = admin_models.Package.objects.create(
            name='nagios-plugins-cert',
            version='1.0.0'
        )
        package3.repos.add(repo)

        package4 = admin_models.Package.objects.create(
            name='emi.dcache.srm-probes',
            version='1.0.1'
        )
        package4.repos.add(repo)

        probe1 = admin_models.Probe.objects.create(
            name='check_oneprovider',
            package=package1,
            description='Each of Onedata services expose an endpoint with '
                        'health data in XML for all worker processes running '
                        'on a given site.',
            comment='Initial version.',
            repository='https://github.com/onedata/nagios-plugins-onedata',
            docurl='https://github.com/onedata/nagios-plugins-onedata/blob/'
                   'master/README.md'
        )

        probe2 = admin_models.Probe.objects.create(
            name='check_ssl_cert',
            package=package2,
            description='A Nagios plugin to check an X.509 certificate.',
            comment='Initial version.',
            repository='https://github.com/matteocorti/check_ssl_cert',
            docurl='https://github.com/matteocorti/check_ssl_cert/blob/master'
                   '/README.md'
        )

        probe3 = admin_models.Probe.objects.create(
            name='CertLifetime-probe',
            package=package3,
            description='Nagios plugin for checking X509 certificate lifetime.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-cert',
            docurl='https://wiki.egi.eu/wiki/ROC_SAM_Tests#hr.srce.CREAMCE-'
                   'CertLifetime'
        )

        probe4 = admin_models.Probe.objects.create(
            name='SRM-probe',
            package=package4,
            description='SRM probe.',
            comment='Initial version.',
            repository='https://github.com/dCache/emi-builds/tree/master/'
                       'srm-probes/src',
            docurl='https://github.com/ARGOeu/samdoc'
        )

        probeversion1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probeversion2 = admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probeversion3 = admin_models.ProbeHistory.objects.create(
            object_id=probe3,
            name=probe3.name,
            package=probe3.package,
            description=probe3.description,
            comment=probe3.comment,
            repository=probe3.repository,
            docurl=probe3.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probeversion4 = admin_models.ProbeHistory.objects.create(
            object_id=probe4,
            name=probe4.name,
            package=probe4.package,
            description=probe4.description,
            comment=probe4.comment,
            repository=probe4.repository,
            docurl=probe4.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        poem_models.Metric.objects.create(
            name='org.onedata.Oneprovider-Health',
            probekey=probeversion1,
            mtype=mtype
        )

        poem_models.Metric.objects.create(
            name='eu.egi.CertValidity',
            probekey=probeversion2,
            mtype=mtype
        )

        poem_models.Metric.objects.create(
            name='hr.srce.SRM2-CertLifetime',
            probekey=probeversion3,
            mtype=mtype
        )

        poem_models.Metric.objects.create(
            name='org.sam.SRM-All',
            probekey=probeversion4,
            mtype=mtype
        )

    def test_get_services(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {'result':
                {
                    'rows': [
                        {
                            'service_category': 'Storage & Data',
                            'service_name': 'EGI DataHub',
                            'service_type': 'org.onedata.oneprovider',
                            'metric': 'org.onedata.Oneprovider-Health',
                            'probe': 'check_oneprovider (3.2.0)'
                        },
                        {
                            'service_category': '',
                            'service_name': '',
                            'service_type': '',
                            'metric': 'eu.egi.CertValidity',
                            'probe': 'check_ssl_cert (1.84.0)'
                        },
                        {
                            'service_category': '',
                            'service_name': 'EGI Online Storage',
                            'service_type': 'SRM',
                            'metric': 'hr.srce.SRM2-CertLifetime',
                            'probe': 'CertLifetime-probe (1.0.0)'
                        },
                        {
                            'service_category': '',
                            'service_name': '',
                            'service_type': '',
                            'metric': 'org.sam.SRM-All',
                            'probe': 'SRM-probe (1.0.1)'
                        }
                    ],
                    'rowspan': {
                        'service_category': [
                            ('Storage & Data', 4 )
                        ],
                        'service_name': [
                            ('EGI DataHub', 2),
                            ('EGI Online Storage', 2)
                        ],
                        'service_type': [
                            ('org.onedata.oneprovider', 2),
                            ('SRM', 2)
                        ],
                        'metric': [
                            ('org.onedata.Oneprovider-Health', 1),
                            ('eu.egi.CertValidity', 1),
                            ('hr.srce.SRM2-CertLifetime', 1),
                            ('org.sam.SRM-All', 1)
                        ],
                        'probe': [
                            ('check_oneprovider (3.2.0)', 1),
                            ('check_ssl_cert (1.84.0)', 1),
                            ('CertLifetime-probe (1.0.0)', 1),
                            ('SRM-probe (1.0.1)', 1)
                        ]
                    }
                }
            }
        )


class ListAggregationsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListAggregations.as_view()
        self.url = '/api/v2/internal/aggregations/'
        self.user = CustUser.objects.create(username='testuser')

        self.aggr1 = poem_models.Aggregation.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.aggr2 = poem_models.Aggregation.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )

        self.group = poem_models.GroupOfAggregations.objects.create(name='EGI')
        poem_models.GroupOfAggregations.objects.create(name='new-group')

        self.ct = ContentType.objects.get_for_model(poem_models.Aggregation)

        data = json.loads(
            serializers.serialize(
                'json', [self.aggr1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'endpoint_group': 'sites',
            'metric_operation': 'AND',
            'profile_operation': 'AND',
            'metric_profile': 'TEST_PROFILE',
            'groups': [
                {
                    'name': 'Group2',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'VOMS',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.aggr1.id,
            serialized_data=json.dumps(data),
            object_repr=self.aggr1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.aggr2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'endpoint_group': 'servicegroups',
            'metric_operation': 'AND',
            'profile_operation': 'AND',
            'metric_profile': 'TEST_PROFILE',
            'groups': [
                {
                    'name': 'Group3',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'VOMS',
                            'operation': 'OR'
                        },
                        {
                            'name': 'argo.api',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.aggr2.id,
            serialized_data=json.dumps(data),
            object_repr=self.aggr2.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct
        )

    @patch('Poem.api.internal_views.aggregationprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_all_aggregations(self, func):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                OrderedDict([
                    ('name', 'ANOTHER-PROFILE'),
                    ('description', ''),
                    ('apiid', '12341234-oooo-kkkk-aaaa-aaeekkccnnee'),
                    ('groupname', '')
                ]),
                OrderedDict([
                    ('name', 'TEST_PROFILE'),
                    ('description', ''),
                    ('apiid', '00000000-oooo-kkkk-aaaa-aaeekkccnnee'),
                    ('groupname', 'EGI')
                ]),
            ]
        )

    @patch('Poem.api.internal_views.aggregationprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_aggregation_by_name(self, func):
        request = self.factory.get(self.url + 'TEST_PROFILE')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'TEST_PROFILE')
        self.assertEqual(
            response.data,
            OrderedDict([
                ('name', 'TEST_PROFILE'),
                ('description', ''),
                ('apiid', '00000000-oooo-kkkk-aaaa-aaeekkccnnee'),
                ('groupname', 'EGI')
            ])
        )

    @patch('Poem.api.internal_views.aggregationprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_aggregation_if_wrong_name(self, func):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_aggregation(self):
        data = {
            'apiid': '12341234-aaaa-kkkk-aaaa-aaeekkccnnee',
            'name': 'new-profile',
            'groupname': 'EGI',
            'endpoint_group': 'sites',
            'metric_operation': 'AND',
            'profile_operation': 'AND',
            'metric_profile': 'TEST_PROFILE',
            'groups': json.dumps([
                {
                    'name': 'Group1',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                }
            ])
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        profile = poem_models.Aggregation.objects.get(name='new-profile')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(profile.name, 'new-profile')
        self.assertEqual(profile.apiid, '12341234-aaaa-kkkk-aaaa-aaeekkccnnee')
        self.assertEqual(profile.groupname, 'EGI')
        history = poem_models.TenantHistory.objects.filter(
            object_id=profile.id, content_type=self.ct
        ).order_by('-date_created')
        self.assertEqual(history.count(), 1)
        serialized_data = json.loads(history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], profile.name)
        self.assertEqual(serialized_data['apiid'], profile.apiid)
        self.assertEqual(serialized_data['groupname'], profile.groupname)
        self.assertEqual(serialized_data['endpoint_group'], 'sites')
        self.assertEqual(serialized_data['metric_operation'], 'AND')
        self.assertEqual(serialized_data['profile_operation'], 'AND')
        self.assertEqual(
            serialized_data['groups'],
            [
                {
                    'name': 'Group1',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        )

    def test_post_aggregations_invalid_data(self):
        data = {'name': 'new-profile'}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_aggregations(self):
        data = {
            'name': 'TEST_PROFILE',
            'apiid': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            'groupname': 'new-group',
            'endpoint_group': 'servicegroups',
            'metric_operation': 'OR',
            'profile_operation': 'AND',
            'metric_profile': 'PROFILE2',
            'groups': json.dumps([
                {
                    'name': 'Group3',
                    'operation': 'OR',
                    'services': [
                        {
                            'name': 'VOMS',
                            'operation': 'AND'
                        }
                    ]
                }
            ])
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = poem_models.Aggregation.objects.get(id=self.aggr1.id)
        self.assertEqual(profile.name, 'TEST_PROFILE')
        self.assertEqual(profile.apiid, '00000000-oooo-kkkk-aaaa-aaeekkccnnee')
        self.assertEqual(profile.groupname, 'new-group')
        history = poem_models.TenantHistory.objects.filter(
            object_id=profile.id, content_type=self.ct
        ).order_by('-date_created')
        self.assertEqual(history.count(), 2)
        serialized_data = json.loads(history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], profile.name)
        self.assertEqual(serialized_data['apiid'], profile.apiid)
        self.assertEqual(serialized_data['groupname'], profile.groupname)
        self.assertEqual(serialized_data['endpoint_group'], 'servicegroups')
        self.assertEqual(serialized_data['metric_operation'], 'OR')
        self.assertEqual(serialized_data['profile_operation'], 'AND')
        self.assertEqual(serialized_data['metric_profile'], 'PROFILE2')
        self.assertEqual(
            serialized_data['groups'],
            [
                {
                    'name': 'Group3',
                    'operation': 'OR',
                    'services': [
                        {
                            'name': 'VOMS',
                            'operation': 'AND'
                        }
                    ]
                }
            ]
        )

    def test_delete_aggregation(self):
        self.assertEqual(
            poem_models.TenantHistory.objects.filter(
                object_id=self.aggr2.id, content_type=self.ct
            ).count(), 1
        )
        request = self.factory.delete(
            self.url + '12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, '12341234-oooo-kkkk-aaaa-aaeekkccnnee')
        profiles = poem_models.Aggregation.objects.all().values_list(
            'name', flat=True
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse('ANOTHER-PROFILE' in profiles)
        self.assertEqual(
            poem_models.TenantHistory.objects.filter(
                object_id=self.aggr2.id, content_type=self.ct
            ).count(), 0
        )

    def test_delete_aggregation_with_wrong_id(self):
        request = self.factory.delete(self.url + 'wrong_id')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'wrong_id')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ListServiceFlavoursAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListAllServiceFlavours.as_view()
        self.url = '/api/v2/internal/serviceflavoursall/'
        self.user = CustUser.objects.create(username='testuser')

        poem_models.ServiceFlavour.objects.create(
            name='org.onedata.oneprovider',
            description='Oneprovider is a Onedata component...'
        )

        poem_models.ServiceFlavour.objects.create(
            name='SRM',
            description='Storage Resource Manager.'
        )

    def test_get_service_flavours(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                OrderedDict([
                    ('name', 'org.onedata.oneprovider'),
                    ('description', 'Oneprovider is a Onedata component...')
                ]),
                OrderedDict([
                    ('name', 'SRM'),
                    ('description', 'Storage Resource Manager.')
                ])
            ]
        )


class ListAllMetricsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListAllMetrics.as_view()
        self.url = '/api/v2/internal/metricsall/'
        self.user = CustUser.objects.create(username='testuser')

        group = poem_models.GroupOfMetrics.objects.create(name='EGI')
        poem_models.GroupOfMetrics.objects.create(name='delete')

        mtype1 = poem_models.MetricType.objects.create(name='Active')
        mtype2 = poem_models.MetricType.objects.create(name='Passive')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)
        package = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package.repos.add(repo)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        probeversion1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username,
        )

        poem_models.Metric.objects.create(
            name='argo.AMS-Check',
            mtype=mtype1,
            probekey=probeversion1,
            group=group,
        )

        poem_models.Metric.objects.create(
            name='org.apel.APEL-Pub',
            group=group,
            mtype=mtype2,
        )

    def test_get_all_metrics(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {'name': 'argo.AMS-Check'},
                {'name': 'org.apel.APEL-Pub'}
            ]
        )


class ListMetricProfilesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricProfiles.as_view()
        self.url = '/api/v2/internal/metricprofiles/'
        self.user = CustUser.objects.create(username='testuser')

        self.ct = ContentType.objects.get_for_model(poem_models.MetricProfiles)

        mp1 = poem_models.MetricProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.mp2 = poem_models.MetricProfiles.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )

        poem_models.GroupOfMetricProfiles.objects.create(name='EGI')
        poem_models.GroupOfMetricProfiles.objects.create(name='new-group')

        data1 = json.loads(
            serializers.serialize(
                'json', [mp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data1[0]['fields'].update({
            'metricinstances': [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['APEL', 'org.apel.APEL-Sync']
            ]
        })

        data2 = json.loads(
            serializers.serialize(
                'json', [self.mp2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data2[0]['fields'].update({
            'metricinstances': []
        })

        poem_models.TenantHistory.objects.create(
            object_id=mp1.id,
            serialized_data=json.dumps(data1),
            object_repr=mp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct
        )

        poem_models.TenantHistory.objects.create(
            object_id=self.mp2.id,
            serialized_data=json.dumps(data2),
            object_repr=self.mp2.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct
        )

    @patch('Poem.api.internal_views.metricprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_all_metric_profiles(self, func):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                OrderedDict([
                    ('name', 'ANOTHER-PROFILE'),
                    ('description', ''),
                    ('apiid', '12341234-oooo-kkkk-aaaa-aaeekkccnnee'),
                    ('groupname', '')
                ]),
                OrderedDict([
                    ('name', 'TEST_PROFILE'),
                    ('description', ''),
                    ('apiid', '00000000-oooo-kkkk-aaaa-aaeekkccnnee'),
                    ('groupname', 'EGI')
                ]),
            ]
        )

    @patch('Poem.api.internal_views.metricprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_metric_profile_by_name(self, func):
        request = self.factory.get(self.url + 'TEST_PROFILE')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'TEST_PROFILE')
        self.assertEqual(
            response.data,
            OrderedDict([
                ('name', 'TEST_PROFILE'),
                ('description', ''),
                ('apiid', '00000000-oooo-kkkk-aaaa-aaeekkccnnee'),
                ('groupname', 'EGI')
            ])
        )

    @patch('Poem.api.internal_views.metricprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_metric_profile_if_wrong_name(self, func):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_metric_profile(self):
        data = {
            "apiid": "12341234-aaaa-kkkk-aaaa-aaeekkccnnee",
            "name": "new-profile",
            "groupname": "EGI",
            "description": "New profile description.",
            "services": [
                {"service": "AMGA", "metric": "org.nagios.SAML-SP"},
                {"service": "APEL", "metric": "org.apel.APEL-Pub"},
                {"service": "APEL", "metric": "org.apel.APEL-Sync"}
            ]
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        profile = poem_models.MetricProfiles.objects.get(name='new-profile')
        history = poem_models.TenantHistory.objects.filter(
            object_id=profile.id, content_type=self.ct
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(profile.name, 'new-profile')
        self.assertEqual(profile.apiid, '12341234-aaaa-kkkk-aaaa-aaeekkccnnee')
        self.assertEqual(profile.groupname, 'EGI')
        self.assertEqual(history.count(), 1)
        self.assertEqual(history[0].comment, 'Initial version.')

    def test_post_metric_profile_invalid_data(self):
        data = {'name': 'new-profile'}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_metric_profile(self):
        data = {
            "name": "TEST_PROFILE",
            "apiid": "00000000-oooo-kkkk-aaaa-aaeekkccnnee",
            "groupname": "new-group",
            "description": "New profile description.",
            "services": [
                {"service": "AMGA", "metric": "org.nagios.SAML-SP"},
                {"service": "APEL", "metric": "org.apel.APEL-Pub"},
                {"service": "APEL", "metric": "org.apel.APEL-Sync"}
            ]
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = poem_models.MetricProfiles.objects.get(name='TEST_PROFILE')
        history = poem_models.TenantHistory.objects.filter(
            object_id=profile.id, content_type=self.ct
        ).order_by('-date_created')
        self.assertEqual(profile.name, 'TEST_PROFILE')
        self.assertEqual(profile.apiid, '00000000-oooo-kkkk-aaaa-aaeekkccnnee')
        self.assertEqual(profile.groupname, 'new-group')
        self.assertEqual(history.count(), 2)
        serialized_data = json.loads(history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], profile.name)
        self.assertEqual(serialized_data['apiid'], profile.apiid)
        self.assertEqual(serialized_data['groupname'], profile.groupname)
        self.assertEqual(
            serialized_data['metricinstances'],
            [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['APEL', 'org.apel.APEL-Sync']
            ]
        )
        self.assertEqual(
            history[0].comment,
            '[{"added": {"fields": ["description"]}}, '
            '{"changed": {"fields": ["groupname"]}}]'
        )

    def test_delete_metric_profile(self):
        request = self.factory.delete(self.url + 'ANOTHER-PROFILE')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'ANOTHER-PROFILE')
        all = poem_models.MetricProfiles.objects.all().values_list(
            'name', flat=True
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse('ANOTHER-PROFILE' in all)
        history = poem_models.TenantHistory.objects.filter(
            object_id=self.mp2.id, content_type=self.ct
        )
        self.assertEqual(history.count(), 0)

    def test_delete_metric_profile_with_wrong_id(self):
        request = self.factory.delete(self.url + 'wrong_id')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'wrong_id')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GetUserProfileForUsernameAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.GetUserprofileForUsername.as_view()
        self.url = '/api/v2/internal/userprofile/'
        self.user = CustUser.objects.create(username='testuser')

        user1 = CustUser.objects.create_user(
            username='username1',
            first_name='First',
            last_name='User',
            email='fuser@example.com',
            is_active=True,
            is_superuser=False
        )

        self.gm = poem_models.GroupOfMetrics.objects.create(
            name='GROUP-metrics'
        )
        poem_models.GroupOfMetrics.objects.create(name='GROUP2-metrics')
        self.ga = poem_models.GroupOfAggregations.objects.create(
            name='GROUP-aggregations'
        )
        poem_models.GroupOfAggregations.objects.create(
            name='GROUP2-aggregations'
        )
        self.gmp = poem_models.GroupOfMetricProfiles.objects.create(
            name='GROUP-metricprofiles'
        )
        self.gtp = poem_models.GroupOfThresholdsProfiles.objects.create(
            name='GROUP-thresholds'
        )
        poem_models.GroupOfThresholdsProfiles.objects.create(
            name='GROUP2-thresholds'
        )

        self.userprofile = poem_models.UserProfile.objects.create(
            user=user1,
            subject='bla',
            displayname='First_User',
            egiid='blablabla'
        )
        self.userprofile.groupsofmetrics.add(self.gm)
        self.userprofile.groupsofaggregations.add(self.ga)
        self.userprofile.groupsofmetricprofiles.add(self.gmp)
        self.userprofile.groupsofthresholdsprofiles.add(self.gtp)

    def test_get_user_profile_for_given_username(self):
        request = self.factory.get(self.url + 'username1')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'username1')
        self.assertEqual(
            response.data,
            OrderedDict([
                ('subject', 'bla'),
                ('egiid', 'blablabla'),
                ('displayname', 'First_User')
            ])
        )

    def test_get_user_profile_if_username_does_not_exist(self):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'User not found'})

    def test_get_user_profile_if_user_profile_does_not_exist(self):
        request = self.factory.get(self.url + 'testuser')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'testuser')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'User profile not found'})

    def test_put_userprofile(self):
        self.assertEqual(self.userprofile.groupsofmetrics.count(), 1)
        self.assertEqual(self.userprofile.groupsofmetricprofiles.count(), 1)
        self.assertEqual(self.userprofile.groupsofaggregations.count(), 1)
        self.assertEqual(self.userprofile.groupsofthresholdsprofiles.count(), 1)
        data = {
            'username': 'username1',
            'displayname': 'Username_1',
            'egiid': 'newegiid',
            'subject': 'newsubject',
            'groupsofaggregations': ['GROUP2-aggregations'],
            'groupsofmetrics': ['GROUP-metrics', 'GROUP2-metrics'],
            'groupsofmetricprofiles': ['GROUP-metricprofiles'],
            'groupsofthresholdsprofiles': ['GROUP2-thresholds']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        userprofile = poem_models.UserProfile.objects.get(
            id=self.userprofile.id
        )
        self.assertEqual(userprofile.displayname, 'Username_1')
        self.assertEqual(userprofile.egiid, 'newegiid')
        self.assertEqual(userprofile.subject, 'newsubject')
        self.assertEqual(userprofile.groupsofaggregations.count(), 1)
        self.assertTrue(
            userprofile.groupsofaggregations.filter(
                name='GROUP2-aggregations'
            ).exists()
        )
        self.assertFalse(
            userprofile.groupsofaggregations.filter(
                name='GROUP-aggregations'
            ).exists()
        )
        self.assertEqual(userprofile.groupsofmetrics.count(), 2)
        self.assertTrue(
            userprofile.groupsofmetrics.filter(
                name='GROUP-metrics'
            ).exists()
        )
        self.assertTrue(
            userprofile.groupsofmetrics.filter(
                name='GROUP2-metrics'
            ).exists()
        )
        self.assertEqual(userprofile.groupsofmetricprofiles.count(), 1)
        self.assertTrue(
            userprofile.groupsofmetricprofiles.filter(
                name='GROUP-metricprofiles'
            ).exists()
        )
        self.assertEqual(userprofile.groupsofthresholdsprofiles.count(), 1)
        self.assertTrue(
            userprofile.groupsofthresholdsprofiles.filter(
                name='GROUP2-thresholds'
            ).exists()
        )
        self.assertFalse(
            userprofile.groupsofthresholdsprofiles.filter(
                name='GROUP-thresholds'
            ).exists()
        )

    def test_post_userprofile(self):
        self.assertEqual(poem_models.UserProfile.objects.all().count(), 1)
        user = CustUser.objects.create_user(
            username='username2',
            first_name='Second',
            last_name='User',
            email='suser@example.com',
            is_active=True,
            is_superuser=False
        )
        data = {
            'username': 'username2',
            'displayname': 'Second_User',
            'subject': 'secondsubject',
            'egiid': 'bla',
            'groupsofaggregations': ['GROUP-aggregations',
                                     'GROUP2-aggregations'],
            'groupsofmetrics': ['GROUP-metrics'],
            'groupsofthresholdsprofiles': [],
            'groupofmetricprofiles': []
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        userprofile = poem_models.UserProfile.objects.get(user=user)
        self.assertEqual(userprofile.displayname, 'Second_User')
        self.assertEqual(userprofile.egiid, 'bla')
        self.assertEqual(userprofile.subject, 'secondsubject')
        self.assertEqual(userprofile.groupsofaggregations.count(), 2)
        self.assertTrue(
            userprofile.groupsofaggregations.filter(
                name='GROUP-aggregations'
            ).exists()
        )
        self.assertTrue(
            userprofile.groupsofaggregations.filter(
                name='GROUP2-aggregations'
            ).exists()
        )
        self.assertEqual(userprofile.groupsofmetrics.count(), 1)
        self.assertTrue(
            userprofile.groupsofmetrics.filter(
                name='GROUP-metrics'
            ).exists()
        )
        self.assertEqual(userprofile.groupsofmetricprofiles.count(), 0)
        self.assertEqual(userprofile.groupsofthresholdsprofiles.count(), 0)


class ListGroupsForGivenUserAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListGroupsForGivenUser.as_view()
        self.url = '/api/v2/internal/usergroups/'
        self.user = CustUser.objects.create(username='testuser')

        user1 = CustUser.objects.create_user(
            username='username1',
            first_name='First',
            last_name='User',
            email='fuser@example.com',
            is_active=True,
            is_superuser=False
        )

        gm = poem_models.GroupOfMetrics.objects.create(name='GROUP-metrics')
        poem_models.GroupOfMetrics.objects.create(name='GROUP2-metrics')
        ga = poem_models.GroupOfAggregations.objects.create(
            name='GROUP-aggregations'
        )
        gmp = poem_models.GroupOfMetricProfiles.objects.create(
            name='GROUP-metricprofiles'
        )
        gtp = poem_models.GroupOfThresholdsProfiles.objects.create(
            name='GROUP-thresholds'
        )

        userprofile = poem_models.UserProfile.objects.create(
            user=user1
        )
        userprofile.groupsofmetrics.add(gm)
        userprofile.groupsofaggregations.add(ga)
        userprofile.groupsofmetricprofiles.add(gmp)
        userprofile.groupsofthresholdsprofiles.add(gtp)

    def test_get_groups_for_given_user(self):
        request = self.factory.get(self.url + 'username1')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'username1')
        self.assertEqual(
            response.data,
            {
                'result': {
                    'aggregations': ['GROUP-aggregations'],
                    'metrics': ['GROUP-metrics'],
                    'metricprofiles': ['GROUP-metricprofiles'],
                    'thresholdsprofiles': ['GROUP-thresholds']
                }
            }
        )

    def test_get_all_groups(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': {
                    'aggregations': ['GROUP-aggregations'],
                    'metrics': ['GROUP-metrics', 'GROUP2-metrics'],
                    'metricprofiles': ['GROUP-metricprofiles'],
                    'thresholdsprofiles': ['GROUP-thresholds']
                }
            }
        )


class ListMetricsInGroupAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricsInGroup.as_view()
        self.url = '/api/v2/internal/metricsgroup/'
        self.user = CustUser.objects.create_user(username='testuser')

        self.group = poem_models.GroupOfMetrics.objects.create(name='EGI')
        group2 = poem_models.GroupOfMetrics.objects.create(name='delete')

        mtype1 = poem_models.MetricType.objects.create(name='Active')
        mtype2 = poem_models.MetricType.objects.create(name='Passive')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)

        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-check_ssl_cert',
            version='1.84.0'
        )
        package2.repos.add(repo)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user='testuser',
            datetime=datetime.datetime.now()
        )

        probe2 = admin_models.Probe.objects.create(
            name='check_ssl_cert',
            package=package2,
            description='A Nagios plugin to check an X.509 certificate.',
            comment='Initial version.',
            repository='https://github.com/matteocorti/check_ssl_cert',
            docurl='https://github.com/matteocorti/check_ssl_cert/blob/master'
                   '/README.md'
        )

        pv1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        pv2 = admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.metric1 = poem_models.Metric.objects.create(
            name='argo.AMS-Check',
            mtype=mtype1,
            probekey=pv1,
            group=self.group,
        )

        self.metric2 = poem_models.Metric.objects.create(
            name='org.apel.APEL-Pub',
            group=self.group,
            mtype=mtype2,
        )

        self.metric3 = poem_models.Metric.objects.create(
            name='eu.egi.CertValidity',
            probekey=pv2,
            mtype=mtype1
        )

        self.metric4 = poem_models.Metric.objects.create(
            name='delete.metric',
            group=group2,
            mtype=mtype2
        )

        self.ct = ContentType.objects.get_for_model(poem_models.Metric)

        self.ver1 = poem_models.TenantHistory.objects.create(
            object_id=self.metric1.id,
            serialized_data=serializers.serialize(
                'json', [self.metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric1.__str__(),
            content_type=self.ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        self.ver2 = poem_models.TenantHistory.objects.create(
            object_id=self.metric2.id,
            serialized_data=serializers.serialize(
                'json', [self.metric2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric2.__str__(),
            content_type=self.ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        self.ver3 = poem_models.TenantHistory.objects.create(
            object_id=self.metric3.id,
            serialized_data=serializers.serialize(
                'json', [self.metric3],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric3.__str__(),
            content_type=self.ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        self.ver4 = poem_models.TenantHistory.objects.create(
            object_id=self.metric4.id,
            serialized_data=serializers.serialize(
                'json', [self.metric4],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric4.__str__(),
            content_type=self.ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

    def test_get_metrics_in_group(self):
        request = self.factory.get(self.url + 'EGI')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'EGI')
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.metric1.id, 'name': 'argo.AMS-Check'},
                    {'id': self.metric2.id, 'name': 'org.apel.APEL-Pub'}
                ]
            }
        )

    def test_get_metric_without_group(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.metric3.id, 'name': 'eu.egi.CertValidity'}
                ]
            }
        )

    def test_get_metric_group_with_no_autorization(self):
        request = self.factory.get(self.url + 'EGI')
        response = self.view(request, 'EGI')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_metrics_with_nonexisting_group(self):
        request = self.factory.get(self.url + 'bla')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'bla')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_metrics_in_group(self):
        data = {'name': 'EGI',
                'items': ['argo.AMS-Check', 'eu.egi.CertValidity']}
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        metric1 = poem_models.Metric.objects.get(name='argo.AMS-Check')
        metric2 = poem_models.Metric.objects.get(name='eu.egi.CertValidity')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ver1 = poem_models.TenantHistory.objects.filter(
            object_id=metric1.id,
            content_type=self.ct
        )
        ver2 = poem_models.TenantHistory.objects.filter(
            object_id=metric2.id,
            content_type=self.ct
        )
        self.assertEqual(ver1.count(), 1)
        self.assertEqual(ver2.count(), 2)
        self.assertEqual(metric1.group.name, 'EGI')
        self.assertEqual(metric2.group.name, 'EGI')
        self.assertEqual(
            json.loads(ver2[0].serialized_data)[0]['fields']['group'][0],
            'EGI'
        )
        self.assertEqual(ver2[0].comment,
                         '[{"added": {"fields": ["group"]}}]')
        self.assertEqual(
            json.loads(ver1[0].serialized_data)[0]['fields']['group'][0],
            'EGI'
        )

    def test_remove_metric_from_group(self):
        self.metric3.group = self.group
        self.metric3.save()
        data = {'name': 'EGI',
                'items': ['eu.egi.CertValidity']}
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        metric1 = poem_models.Metric.objects.get(name='argo.AMS-Check')
        metric2 = poem_models.Metric.objects.get(name='eu.egi.CertValidity')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(metric1.group, None)
        self.assertEqual(metric2.group.name, 'EGI')

    def test_post_metric_group_without_metrics(self):
        self.assertEqual(poem_models.GroupOfMetrics.objects.all().count(), 2)
        data = {'name': 'new_name',
                'items': []}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(poem_models.GroupOfMetrics.objects.all().count(), 3)

    def test_post_metric_group_with_metrics(self):
        self.assertEqual(poem_models.GroupOfMetrics.objects.all().count(), 2)
        data = {'name': 'new_name',
                'items': ['eu.egi.CertValidity']}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(poem_models.GroupOfMetrics.objects.all().count(), 3)
        metric = poem_models.Metric.objects.get(name='eu.egi.CertValidity')
        self.assertEqual(metric.group.name, 'new_name')

    def test_post_metrics_group_with_name_that_already_exists(self):
        data = {'name': 'EGI',
                'items': [self.metric1.name]}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Group of metrics with this name already exists.'}
        )

    def test_delete_metric_group(self):
        self.assertEqual(poem_models.GroupOfMetrics.objects.all().count(), 2)
        request = self.factory.delete(self.url + 'delete')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'delete')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(poem_models.GroupOfMetrics.objects.all().count(), 1)
        self.assertRaises(
            poem_models.GroupOfMetrics.DoesNotExist,
            poem_models.GroupOfMetrics.objects.get,
            name='delete'
        )
        metric = poem_models.Metric.objects.get(name='delete.metric')
        self.assertEqual(metric.group, None)

    def test_delete_nonexisting_metric_group(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_metric_group_without_specifying_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListAggregationsInGroupAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListAggregationsInGroup.as_view()
        self.url = '/api/v2/internal/aggregationsgroup/'
        self.user = CustUser.objects.create_user(username='testuser')

        self.aggr1 = poem_models.Aggregation.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.aggr2 = poem_models.Aggregation.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )

        self.aggr3 = poem_models.Aggregation.objects.create(
            name='DELETE_PROFILE',
            apiid='12341234-hhhh-kkkk-aaaa-aaeekkccnnee',
            groupname='delete'
        )

        self.group = poem_models.GroupOfAggregations.objects.create(name='EGI')
        group2 = poem_models.GroupOfAggregations.objects.create(name='delete')
        self.group.aggregations.add(self.aggr1)
        group2.aggregations.add(self.aggr3)

    def test_get_aggregations_in_group(self):
        request = self.factory.get(self.url + 'EGI')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'EGI')
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.aggr1.id, 'name': 'TEST_PROFILE'}
                ]
            }
        )

    def test_get_aggregations_in_case_no_authorization(self):
        request = self.factory.get(self.url + 'EGI')
        response = self.view(request, 'EGI')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_aggregation_without_group(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.aggr2.id, 'name': 'ANOTHER-PROFILE'}
                ]
            }
        )

    def test_add_aggregation_profile_in_group(self):
        self.assertEqual(self.group.aggregations.count(), 1)
        data = {'name': 'EGI',
                'items': ['TEST_PROFILE', 'ANOTHER-PROFILE']}
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        aggr1 = poem_models.Aggregation.objects.get(name='TEST_PROFILE')
        aggr2 = poem_models.Aggregation.objects.get(name='ANOTHER-PROFILE')
        self.assertEqual(aggr1.groupname, 'EGI')
        self.assertEqual(aggr2.groupname, 'EGI')
        self.assertEqual(self.group.aggregations.count(), 2)

    def test_remove_aggregation_profile_from_group(self):
        self.group.aggregations.add(self.aggr2)
        self.assertEqual(self.group.aggregations.count(), 2)
        data = {
            'name': 'EGI',
            'items': ['ANOTHER-PROFILE']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        aggr1 = poem_models.Aggregation.objects.get(name='TEST_PROFILE')
        aggr2 = poem_models.Aggregation.objects.get(name='ANOTHER-PROFILE')
        self.assertEqual(aggr1.groupname, '')
        self.assertEqual(aggr2.groupname, 'EGI')
        self.assertEqual(self.group.aggregations.count(), 1)

    def test_post_aggregation_group_without_aggregation(self):
        self.assertEqual(
            poem_models.GroupOfAggregations.objects.all().count(), 2
        )
        data = {'name': 'new_name',
                'items': []}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.GroupOfAggregations.objects.all().count(), 3
        )
        group = poem_models.GroupOfAggregations.objects.get(name='new_name')
        self.assertEqual(group.aggregations.count(), 0)

    def test_post_aggregation_group_with_aggregation(self):
        self.assertEqual(
            poem_models.GroupOfAggregations.objects.all().count(), 2
        )
        data = {'name': 'new_name',
                'items': ['ANOTHER-PROFILE']}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.GroupOfAggregations.objects.all().count(), 3
        )
        group = poem_models.GroupOfAggregations.objects.get(name='new_name')
        self.assertEqual(group.aggregations.count(), 1)
        aggr1 = poem_models.Aggregation.objects.get(name='TEST_PROFILE')
        aggr2 = poem_models.Aggregation.objects.get(name='ANOTHER-PROFILE')
        self.assertEqual(aggr1.groupname, 'EGI')
        self.assertEqual(aggr2.groupname, 'new_name')

    def test_post_aggregation_group_with_name_that_already_exists(self):
        data = {'name': 'EGI',
                'items': [self.aggr1.name]}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Group of aggregations with this name already exists.'}
        )

    def test_delete_aggregation_group(self):
        self.assertEqual(poem_models.GroupOfAggregations.objects.all().count(),
                         2)
        request = self.factory.delete(self.url + 'delete')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'delete')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(poem_models.GroupOfAggregations.objects.all().count(),
                         1)
        self.assertRaises(
            poem_models.GroupOfAggregations.DoesNotExist,
            poem_models.GroupOfAggregations.objects.get,
            name='delete'
        )
        aggr = poem_models.Aggregation.objects.get(name='DELETE_PROFILE')
        self.assertEqual(aggr.groupname, '')

    def test_delete_nonexisting_aggregation_group(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_aggregation_group_without_specifying_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListMetricProfilesInGroupAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricProfilesInGroup.as_view()
        self.url = '/api/v2/internal/metricprofilesgroup/'
        self.user = CustUser.objects.create(username='testuser')

        self.mp1 = poem_models.MetricProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.mp2 = poem_models.MetricProfiles.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )

        self.mp3 = poem_models.MetricProfiles.objects.create(
            name='DELETE_PROFILE',
            apiid='12341234-hhhh-kkkk-aaaa-aaeekkccnnee',
            groupname='delete'
        )

        self.group = poem_models.GroupOfMetricProfiles.objects.create(
            name='EGI'
        )
        group2 = poem_models.GroupOfMetricProfiles.objects.create(name='delete')

        self.group.metricprofiles.add(self.mp1)
        group2.metricprofiles.add(self.mp3)

    def test_get_metric_profiles_in_group(self):
        request = self.factory.get(self.url + 'EGI')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'EGI')
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.mp1.id, 'name': 'TEST_PROFILE'}
                ]
            }
        )

    def test_get_metric_profiles_in_group_in_case_no_authorization(self):
        request = self.factory.get(self.url + 'EGI')
        response = self.view(request, 'EGI')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_metric_profiles_without_group(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.mp2.id, 'name': 'ANOTHER-PROFILE'}
                ]
            }
        )

    def test_add_metric_profile_in_group(self):
        self.assertEqual(self.group.metricprofiles.count(), 1)
        data = {'name': 'EGI',
                'items': ['TEST_PROFILE', 'ANOTHER-PROFILE']}
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mp1 = poem_models.MetricProfiles.objects.get(name='TEST_PROFILE')
        mp2 = poem_models.MetricProfiles.objects.get(name='ANOTHER-PROFILE')
        self.assertEqual(mp1.groupname, 'EGI')
        self.assertEqual(mp2.groupname, 'EGI')
        self.assertEqual(self.group.metricprofiles.count(), 2)

    def test_remove_metric_profile_from_group(self):
        self.group.metricprofiles.add(self.mp2)
        self.assertEqual(self.group.metricprofiles.all().count(), 2)
        data = {
            'name': 'EGI',
            'items': ['ANOTHER-PROFILE']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mp1 = poem_models.MetricProfiles.objects.get(name='TEST_PROFILE')
        mp2 = poem_models.MetricProfiles.objects.get(name='ANOTHER-PROFILE')
        self.assertEqual(mp1.groupname, '')
        self.assertEqual(mp2.groupname, 'EGI')
        self.assertEqual(self.group.metricprofiles.count(), 1)

    def test_post_metric_profile_group_without_metric_profile(self):
        self.assertEqual(
            poem_models.GroupOfMetricProfiles.objects.all().count(), 2
        )
        data = {'name': 'new_name',
                'items': []}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.GroupOfMetricProfiles.objects.all().count(), 3
        )
        group = poem_models.GroupOfMetricProfiles.objects.get(name='new_name')
        self.assertEqual(group.metricprofiles.count(), 0)

    def test_post_metric_profile_group_with_metric_profile(self):
        self.assertEqual(
            poem_models.GroupOfMetricProfiles.objects.all().count(), 2
        )
        data = {'name': 'new_name',
                'items': ['ANOTHER-PROFILE']}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.GroupOfMetricProfiles.objects.all().count(), 3
        )
        group = poem_models.GroupOfMetricProfiles.objects.get(name='new_name')
        self.assertEqual(group.metricprofiles.count(), 1)
        mp1 = poem_models.MetricProfiles.objects.get(name='TEST_PROFILE')
        mp2 = poem_models.MetricProfiles.objects.get(name='ANOTHER-PROFILE')
        self.assertEqual(mp1.groupname, 'EGI')
        self.assertEqual(mp2.groupname, 'new_name')

    def test_post_metric_profile_group_with_name_that_already_exists(self):
        data = {'name': 'EGI',
                'items': [self.mp1.name]}
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Metric profiles group with this name already exists.'}
        )

    def test_delete_metric_profile_group(self):
        self.assertEqual(
            poem_models.GroupOfMetricProfiles.objects.all().count(), 2
        )
        request = self.factory.delete(self.url + 'delete')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'delete')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            poem_models.GroupOfMetricProfiles.objects.all().count(), 1
        )
        self.assertRaises(
            poem_models.GroupOfMetrics.DoesNotExist,
            poem_models.GroupOfMetrics.objects.get,
            name='delete'
        )
        mp = poem_models.MetricProfiles.objects.get(name='DELETE_PROFILE')
        self.assertEqual(mp.groupname, '')

    def test_delete_nonexisting_metric_profile_group(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_metric_profile_group_without_specifying_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListMetricAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetric.as_view()
        self.url = '/api/v2/internal/metric/'
        self.user = CustUser.objects.create_user(username='testuser')

        mtype1 = poem_models.MetricType.objects.create(name='Active')
        mtype2 = poem_models.MetricType.objects.create(name='Passive')

        group = poem_models.GroupOfMetrics.objects.create(name='EGI')
        poem_models.GroupOfMetrics.objects.create(name='EUDAT')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)
        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        self.probeversion1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probe1.package = package2
        probe1.comment = 'Updated version.'
        probe1.save()

        self.probeversion2 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Updated version.',
            version_user=self.user.username
        )

        self.metric1 = poem_models.Metric.objects.create(
            name='argo.AMS-Check',
            mtype=mtype1,
            probekey=self.probeversion1,
            group=group,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        self.metric2 = poem_models.Metric.objects.create(
            name='org.apel.APEL-Pub',
            flags='["OBSESS 1", "PASSIVE 1"]',
            group=group,
            mtype=mtype2,
        )

        self.ct = ContentType.objects.get_for_model(poem_models.Metric)

        poem_models.TenantHistory.objects.create(
            object_id=self.metric1.id,
            object_repr=self.metric1.__str__(),
            serialized_data=serializers.serialize(
                'json', [self.metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            date_created=datetime.datetime.now(),
            user=self.user.username,
            comment='Initial version.',
            content_type=self.ct
        )

        poem_models.TenantHistory.objects.create(
            object_id=self.metric2.id,
            object_repr=self.metric2.__str__(),
            serialized_data=serializers.serialize(
                'json', [self.metric2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            date_created=datetime.datetime.now(),
            user=self.user.username,
            comment='Initial version.',
            content_type=self.ct
        )

    def test_get_metric_list(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.metric1.id,
                    'name': 'argo.AMS-Check',
                    'mtype': 'Active',
                    'probeversion': 'ams-probe (0.1.7)',
                    'group': 'EGI',
                    'parent': '',
                    'probeexecutable': 'ams-probe',
                    'config': [
                        {
                            'key': 'maxCheckAttempts',
                            'value': '3'
                        },
                        {
                            'key': 'timeout',
                            'value': '60'
                        },
                        {
                            'key': 'path',
                            'value': '/usr/libexec/argo-monitoring/probes/argo'
                        },
                        {
                            'key': 'interval',
                            'value': '5'
                        },
                        {
                            'key': 'retryInterval',
                            'value': '3'
                        }
                    ],
                    'attribute': [
                        {
                            'key': 'argo.ams_TOKEN',
                            'value': '--token'
                        }
                    ],
                    'dependancy': [],
                    'flags': [
                        {
                            'key': 'OBSESS',
                            'value': '1'
                        }
                    ],
                    'files': [],
                    'parameter': [
                        {
                            'key': '--project',
                            'value': 'EGI'
                        }
                    ],
                    'fileparameter': []
                },
                {
                    'id': self.metric2.id,
                    'name': 'org.apel.APEL-Pub',
                    'mtype': 'Passive',
                    'probeversion': '',
                    'group': 'EGI',
                    'parent': '',
                    'probeexecutable': '',
                    'config': [],
                    'attribute': [],
                    'dependancy': [],
                    'flags': [
                        {
                            'key': 'OBSESS',
                            'value': '1'
                        },
                        {
                            'key': 'PASSIVE',
                            'value': '1'
                        }
                    ],
                    'files': [],
                    'parameter': [],
                    'fileparameter': []
                }
            ]
        )

    def test_get_metric_by_name(self):
        request = self.factory.get(self.url + 'argo.AMS-Check')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'argo.AMS-Check')
        self.assertEqual(
            response.data,
            {
                'id': self.metric1.id,
                'name': 'argo.AMS-Check',
                'mtype': 'Active',
                'probeversion': 'ams-probe (0.1.7)',
                'group': 'EGI',
                'parent': '',
                'probeexecutable': 'ams-probe',
                'config': [
                    {
                        'key': 'maxCheckAttempts',
                        'value': '3'
                    },
                    {
                        'key': 'timeout',
                        'value': '60'
                    },
                    {
                        'key': 'path',
                        'value': '/usr/libexec/argo-monitoring/probes/argo'
                    },
                    {
                        'key': 'interval',
                        'value': '5'
                    },
                    {
                        'key': 'retryInterval',
                        'value': '3'
                    }
                ],
                'attribute': [
                    {
                        'key': 'argo.ams_TOKEN',
                        'value': '--token'
                    }
                ],
                'dependancy': [],
                'flags': [
                    {
                        'key': 'OBSESS',
                        'value': '1'
                    }
                ],
                'files': [],
                'parameter': [
                    {
                        'key': '--project',
                        'value': 'EGI'
                    }
                ],
                'fileparameter': []
            }
        )

    def test_get_metric_by_nonexisting_name(self):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Metric not found'})

    def test_inline_metric_for_db_function(self):
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path',
             'value': '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        res = inline_metric_for_db(conf)
        self.assertEqual(
            res,
            '["maxCheckAttempts 4", "timeout 70", '
             '"path /usr/libexec/argo-monitoring/probes/argo", '
             '"interval 6", "retryInterval 4"]'
        )

    @patch('Poem.api.internal_views.metrics.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_metric(self, func):
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path',
             'value': '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        attribute = [
            {'key': 'argo.ams_TOKEN2', 'value': '--token'},
            {'key': 'mock_attribute', 'value': 'attr'}
        ]
        data = {
            'name': 'argo.AMS-Check',
            'mtype': 'Active',
            'group': 'EUDAT',
            'parent': '',
            'probeversion': 'ams-probe (0.1.11)',
            'probeexecutable': 'ams-probe',
            'config': json.dumps(conf),
            'attribute': json.dumps(attribute),
            'dependancy': '[{"key": "", "value": ""}]',
            'flags': '[{"key": "OBSESS", "value": "1"}]',
            'files': '[{"key": "", "value": ""}]',
            'parameter': '[{"key": "", "value": ""}]',
            'fileparameter': '[{"key": "", "value": ""}]'
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        metric = poem_models.Metric.objects.get(name='argo.AMS-Check')
        versions = poem_models.TenantHistory.objects.filter(
            object_id=metric.id, content_type=self.ct
        )
        self.assertEqual(versions.count(), 2)
        serialized_data = json.loads(
            versions[0].serialized_data
        )[0]['fields']
        self.assertEqual(metric.mtype.name, 'Active')
        self.assertEqual(metric.probekey, self.probeversion2)
        self.assertEqual(metric.group.name, 'EUDAT')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["ams-probe"]')
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 6", "retryInterval 4"]')
        self.assertEqual(
            metric.attribute,
            '["argo.ams_TOKEN2 --token", "mock_attribute attr"]'
        )
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '')
        self.assertEqual(metric.fileparameter, '')
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], [metric.mtype.name])
        self.assertEqual(
            serialized_data['probekey'],
            [metric.probekey.name, metric.probekey.package.version]
        )
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    @patch('Poem.api.internal_views.metrics.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_passive_metric(self, func):
        data = {
            'name': 'org.apel.APEL-Pub',
            'mtype': 'Passive',
            'probeversion': '',
            'group': 'EUDAT',
            'parent': 'test-parent',
            'probeexecutable': 'ams-probe',
            'config': '[{"key": "", "value": ""}]',
            'attribute': '[{"key": "", "value": ""}]',
            'dependancy': '[{"key": "", "value": ""}]',
            'flags': '[{"key": "PASSIVE", "value": "1"}]',
            'files': '[{"key": "", "value": ""}]',
            'parameter': '[{"key": "", "value": ""}]',
            'fileparameter': '[{"key": "", "value": ""}]'
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        metric = poem_models.Metric.objects.get(name='org.apel.APEL-Pub')
        versions = poem_models.TenantHistory.objects.filter(
            object_id=metric.id, content_type=self.ct
        )
        self.assertEqual(versions.count(), 2)
        serialized_data = json.loads(
            versions[0].serialized_data
        )[0]['fields']
        self.assertEqual(metric.mtype.name, 'Passive')
        self.assertEqual(metric.probekey, None)
        self.assertEqual(metric.group.name, 'EUDAT')
        self.assertEqual(metric.parent, '["test-parent"]')
        self.assertEqual(metric.probeexecutable, '')
        self.assertEqual(metric.config, '')
        self.assertEqual(metric.attribute, '')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["PASSIVE 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '')
        self.assertEqual(metric.fileparameter, '')
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], [metric.mtype.name])
        self.assertEqual(serialized_data['probekey'], None)
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    def test_delete_metric(self):
        self.assertEqual(poem_models.Metric.objects.all().count(), 2)
        request = self.factory.delete(self.url + 'org.apel.APEL-Pub')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'org.apel.APEL-Pub')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(poem_models.Metric.objects.all().count(), 1)

    def test_delete_nonexisting_metric(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_metric_without_specifying_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListMetricTypesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricTypes.as_view()
        self.url = '/api/v2/internal/mtypes/'
        self.user = CustUser.objects.create(username='testuser')

        poem_models.MetricType.objects.create(name='Active')
        poem_models.MetricType.objects.create(name='Passive')

    def test_get_tags(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            [r for r in response.data],
            [
                'Active',
                'Passive',
            ]
        )


class ListGroupsForUserAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListGroupsForUser.as_view()
        self.url = '/api/v2/internal/groups/'
        self.user = CustUser.objects.create_user(username='testuser')
        self.superuser = CustUser.objects.create_user(
            username='superuser', is_superuser=True
        )

        poem_models.GroupOfMetrics.objects.create(name='metricgroup1')
        gm1 = poem_models.GroupOfMetrics.objects.create(name='metricgroup2')

        poem_models.GroupOfMetricProfiles.objects.create(
            name='metricprofilegroup1'
        )
        gmp1 = poem_models.GroupOfMetricProfiles.objects.create(
            name='metricprofilegroup2'
        )

        poem_models.GroupOfAggregations.objects.create(name='aggrgroup1')
        ga1 = poem_models.GroupOfAggregations.objects.create(name='aggrgroup2')

        poem_models.GroupOfThresholdsProfiles.objects.create(
            name='thresholdsgroup1'
        )
        gtp1 = poem_models.GroupOfThresholdsProfiles.objects.create(
            name='thresholdsgroup2'
        )

        userprofile = poem_models.UserProfile.objects.create(user=self.user)
        userprofile.groupsofmetrics.add(gm1)
        userprofile.groupsofmetricprofiles.add(gmp1)
        userprofile.groupsofaggregations.add(ga1)
        userprofile.groupsofthresholdsprofiles.add(gtp1)

    def test_list_all_groups(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.superuser)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': {
                    'aggregations': ['aggrgroup1', 'aggrgroup2'],
                    'metrics': ['metricgroup1', 'metricgroup2'],
                    'metricprofiles': ['metricprofilegroup1',
                                       'metricprofilegroup2'],
                    'thresholdsprofiles': ['thresholdsgroup1',
                                           'thresholdsgroup2']
                }
            }
        )

    def test_list_groups_for_user_that_is_not_superuser(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': {
                    'aggregations': ['aggrgroup2'],
                    'metrics': ['metricgroup2'],
                    'metricprofiles': ['metricprofilegroup2'],
                    'thresholdsprofiles': ['thresholdsgroup2']
                }
            }
        )

    def test_get_aggregation_groups_for_superuser(self):
        request = self.factory.get(self.url + 'aggregations')
        force_authenticate(request, user=self.superuser)
        response = self.view(request, 'aggregations')
        self.assertEqual(
            response.data,
            ['aggrgroup1', 'aggrgroup2']
        )

    def test_get_metric_groups_for_superuser(self):
        request = self.factory.get(self.url + 'metrics')
        force_authenticate(request, user=self.superuser)
        response = self.view(request, 'metrics')
        self.assertEqual(
            response.data,
            ['metricgroup1', 'metricgroup2']
        )

    def test_get_metric_profile_groups_for_superuser(self):
        request = self.factory.get(self.url + 'metricprofiles')
        force_authenticate(request, user=self.superuser)
        response = self.view(request, 'metricprofiles')
        self.assertEqual(
            response.data,
            ['metricprofilegroup1', 'metricprofilegroup2']
        )

    def test_get_thresholds_profiles_groups_for_superuser(self):
        request = self.factory.get(self.url + 'thresholdsprofiles')
        force_authenticate(request, user=self.superuser)
        response = self.view(request, 'thresholdsprofiles')
        self.assertEqual(
            response.data,
            ['thresholdsgroup1', 'thresholdsgroup2']
        )

    def test_get_aggregation_groups_for_basic_user(self):
        request = self.factory.get(self.url + 'aggregations')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'aggregations')
        self.assertEqual(
            response.data,
            ['aggrgroup2']
        )

    def test_get_metric_groups_for_basic_user(self):
        request = self.factory.get(self.url + 'metrics')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metrics')
        self.assertEqual(
            response.data,
            ['metricgroup2']
        )

    def test_get_metric_profile_groups_for_basic_user(self):
        request = self.factory.get(self.url + 'metricprofiles')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metricprofiles')
        self.assertEqual(
            response.data,
            ['metricprofilegroup2']
        )

    def test_get_thresholds_profiles_groups_for_basic_user(self):
        request = self.factory.get(self.url + 'thresholdsprofiles')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'thresholdsprofiles')
        self.assertEqual(
            response.data,
            ['thresholdsgroup2']
        )


class GetConfigOptionsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.GetConfigOptions.as_view()
        self.url = '/api/v2/internal/config_options/'
        self.user = CustUser.objects.create(username='testuser')

    @patch('Poem.api.internal_views.app.saml_login_string',
           return_value='Log in using B2ACCESS')
    @patch('Poem.api.internal_views.app.tenant_from_request',
           return_value='Tenant')
    def test_get_config_options(self, *args):
        with self.settings(WEBAPI_METRIC='https://metric.profile.com',
                           WEBAPI_AGGREGATION='https://aggregations.com',
                           WEBAPI_THRESHOLDS='https://thresholds.com'):
            request = self.factory.get(self.url)
            response = self.view(request)
            self.assertEqual(
                response.data,
                {
                    'result': {
                        'saml_login_string': 'Log in using B2ACCESS',
                        'webapimetric': 'https://metric.profile.com',
                        'webapiaggregation': 'https://aggregations.com',
                        'webapithresholds': 'https://thresholds.com',
                        'tenant_name': 'Tenant'
                    }
                }
            )


class ListVersionsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListVersions.as_view()
        self.url = '/api/v2/internal/version/'
        self.user = CustUser.objects.create_user(username='testuser')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)

        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        package2.repos.add(repo)

        self.probe1 = admin_models.Probe.objects.create(
            name='poem-probe',
            package=package1,
            description='Probe inspects POEM service.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user=self.user.username,
            datetime=datetime.datetime.now()
        )

        self.ver1 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.probe1.name = 'poem-probe-new'
        self.probe1.package = package2
        self.probe1.comment = 'This version added: Check POEM metric ' \
                              'configuration API'
        self.probe1.description = 'Probe inspects new POEM service.'
        self.probe1.repository = 'https://github.com/ARGOeu/nagios-plugins-' \
                                 'argo2'
        self.probe1.docurl = 'https://github.com/ARGOeu/nagios-plugins-argo2/' \
                             'blob/master/README.md'
        self.probe1.save()

        self.ver2 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='[{"changed": {"fields": ["name", '
                            '"comment", "description", "repository", '
                            '"docurl"]}}]'
        )

        admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user=self.user.username,
            datetime=datetime.datetime.now()
        )

        probe2 = admin_models.Probe.objects.create(
            name='ams-publisher-probe',
            package=package2,
            description='Probe is inspecting AMS publisher',
            comment='Initial version',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user=self.user.username,
            datetime=datetime.datetime.now()
        )

        self.ver3 = admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.mtype1 = admin_models.MetricTemplateType.objects.create(
            name='Active'
        )
        self.mtype2 = admin_models.MetricTemplateType.objects.create(
            name='Passive'
        )

        self.metrictemplate1 = admin_models.MetricTemplate.objects.create(
            name='argo.POEM-API-MON',
            mtype=self.mtype1,
            probekey=self.ver1,
            probeexecutable='["poem-probe"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 5"]',
            attribute='["POEM_PROFILE -r", "NAGIOS_HOST_CERT --cert",'
                      '"NAGIOS_HOST_KEY --key"]',
        )

        self.ver4 = admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate1,
            name=self.metrictemplate1.name,
            mtype=self.metrictemplate1.mtype,
            probekey=self.metrictemplate1.probekey,
            probeexecutable=self.metrictemplate1.probeexecutable,
            config=self.metrictemplate1.config,
            attribute=self.metrictemplate1.attribute,
            dependency=self.metrictemplate1.dependency,
            flags=self.metrictemplate1.flags,
            files=self.metrictemplate1.files,
            parameter=self.metrictemplate1.parameter,
            fileparameter=self.metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.metrictemplate1.name = 'argo.POEM-API-MON-new'
        self.metrictemplate1.probekey = self.ver2
        self.metrictemplate1.save()

        self.ver5 = admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate1,
            name=self.metrictemplate1.name,
            mtype=self.metrictemplate1.mtype,
            probekey=self.metrictemplate1.probekey,
            probeexecutable=self.metrictemplate1.probeexecutable,
            config=self.metrictemplate1.config,
            attribute=self.metrictemplate1.attribute,
            dependency=self.metrictemplate1.dependency,
            flags=self.metrictemplate1.flags,
            files=self.metrictemplate1.files,
            parameter=self.metrictemplate1.parameter,
            fileparameter=self.metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment=json.dumps(
                [{'changed': {'fields': ['name', 'probekey']}}]
            ),
            version_user=self.user.username
        )

        self.metrictemplate2 = admin_models.MetricTemplate.objects.create(
            name='org.apel.APEL-Pub',
            mtype=self.mtype2,
            flags='["OBSESS 1", "PASSIVE 1"]'
        )

        self.ver6 = admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate2,
            name=self.metrictemplate2.name,
            mtype=self.metrictemplate2.mtype,
            probekey=self.metrictemplate2.probekey,
            probeexecutable=self.metrictemplate2.probeexecutable,
            config=self.metrictemplate2.config,
            attribute=self.metrictemplate2.attribute,
            dependency=self.metrictemplate2.dependency,
            flags=self.metrictemplate2.flags,
            files=self.metrictemplate2.files,
            parameter=self.metrictemplate2.parameter,
            fileparameter=self.metrictemplate2.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.metrictemplate2.name = 'org.apel.APEL-Pub-new'
        self.metrictemplate2.save()

        self.ver7 = admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate2,
            name=self.metrictemplate2.name,
            mtype=self.metrictemplate2.mtype,
            probekey=self.metrictemplate2.probekey,
            probeexecutable=self.metrictemplate2.probeexecutable,
            config=self.metrictemplate2.config,
            attribute=self.metrictemplate2.attribute,
            dependency=self.metrictemplate2.dependency,
            flags=self.metrictemplate2.flags,
            files=self.metrictemplate2.files,
            parameter=self.metrictemplate2.parameter,
            fileparameter=self.metrictemplate2.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment=json.dumps([{'changed': {'fields': ['name']}}]),
            version_user=self.user.username
        )

    def test_get_versions_of_probes(self):
        request = self.factory.get(self.url + 'probe/poem-probe-new')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'probe', 'poem-probe-new')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver2.id,
                    'object_repr': 'poem-probe-new (0.1.11)',
                    'fields': {
                        'name': 'poem-probe-new',
                        'version': '0.1.11',
                        'package': 'nagios-plugins-argo (0.1.11)',
                        'description': 'Probe inspects new POEM service.',
                        'comment': 'This version added: Check POEM metric '
                                   'configuration API',
                        'repository': 'https://github.com/ARGOeu/nagios-'
                                      'plugins-argo2',
                        'docurl': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo2/blob/master/README.md'
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                            self.ver2.date_created, '%Y-%m-%d %H:%M:%S'
                        ),
                    'comment': 'Changed name, comment, description, '
                               'repository and docurl.',
                    'version': '0.1.11'
                },
                {
                    'id': self.ver1.id,
                    'object_repr': 'poem-probe (0.1.7)',
                    'fields': {
                        'name': 'poem-probe',
                        'version': '0.1.7',
                        'package': 'nagios-plugins-argo (0.1.7)',
                        'description': 'Probe inspects POEM service.',
                        'comment': 'Initial version.',
                        'repository': 'https://github.com/ARGOeu/nagios-'
                                      'plugins-argo',
                        'docurl': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo/blob/master/README.md'
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver1.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': '0.1.7'
                }
            ]
        )

    def test_get_versions_of_probes_given_old_version_name(self):
        request = self.factory.get(self.url + 'probe/poem-probe')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'probe', 'poem-probe')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver2.id,
                    'object_repr': 'poem-probe-new (0.1.11)',
                    'fields': {
                        'name': 'poem-probe-new',
                        'version': '0.1.11',
                        'package': 'nagios-plugins-argo (0.1.11)',
                        'description': 'Probe inspects new POEM service.',
                        'comment': 'This version added: Check POEM metric '
                                   'configuration API',
                        'repository': 'https://github.com/ARGOeu/nagios-'
                                      'plugins-argo2',
                        'docurl': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo2/blob/master/README.md'
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                            self.ver2.date_created, '%Y-%m-%d %H:%M:%S'
                        ),
                    'comment': 'Changed name, comment, description, '
                               'repository and docurl.',
                    'version': '0.1.11'
                },
                {
                    'id': self.ver1.id,
                    'object_repr': 'poem-probe (0.1.7)',
                    'fields': {
                        'name': 'poem-probe',
                        'version': '0.1.7',
                        'package': 'nagios-plugins-argo (0.1.7)',
                        'description': 'Probe inspects POEM service.',
                        'comment': 'Initial version.',
                        'repository': 'https://github.com/ARGOeu/nagios-'
                                      'plugins-argo',
                        'docurl': 'https://github.com/ARGOeu/nagios-plugins-'
                                  'argo/blob/master/README.md'
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver1.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': '0.1.7'
                }
            ]
        )

    def test_get_versions_of_metric_template(self):
        request = self.factory.get(self.url +
                                   'metrictemplate/argo.POEM-API-MON-new')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metrictemplate', 'argo.POEM-API-MON-new')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver5.id,
                    'object_repr':
                        'argo.POEM-API-MON-new [poem-probe-new (0.1.11)]',
                    'fields': {
                        'name': 'argo.POEM-API-MON-new',
                        'mtype': self.mtype1.name,
                        'probeversion': 'poem-probe-new (0.1.11)',
                        'parent': '',
                        'probeexecutable': 'poem-probe',
                        'config': [
                            {'key': 'maxCheckAttempts', 'value': '3'},
                            {'key': 'timeout', 'value': '60'},
                            {'key': 'path',
                             'value':
                                 '/usr/libexec/argo-monitoring/probes/argo'},
                            {'key': 'interval', 'value': '5'},
                            {'key': 'retryInterval', 'value': '5'}
                        ],
                        'attribute': [
                            {'key': 'POEM_PROFILE', 'value': '-r'},
                            {'key': 'NAGIOS_HOST_CERT', 'value': '--cert'},
                            {'key': 'NAGIOS_HOST_KEY', 'value': '--key'},
                        ],
                        'dependency': [],
                        'flags': [],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver5.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Changed name and probekey.',
                    'version': '0.1.11'
                },
                {
                    'id': self.ver4.id,
                    'object_repr':
                        'argo.POEM-API-MON [poem-probe (0.1.7)]',
                    'fields': {
                        'name': 'argo.POEM-API-MON',
                        'mtype': self.mtype1.name,
                        'probeversion': 'poem-probe (0.1.7)',
                        'parent': '',
                        'probeexecutable': 'poem-probe',
                        'config': [
                            {'key': 'maxCheckAttempts', 'value': '3'},
                            {'key': 'timeout', 'value': '60'},
                            {'key': 'path',
                             'value':
                                 '/usr/libexec/argo-monitoring/probes/argo'},
                            {'key': 'interval', 'value': '5'},
                            {'key': 'retryInterval', 'value': '5'}
                        ],
                        'attribute': [
                            {'key': 'POEM_PROFILE', 'value': '-r'},
                            {'key': 'NAGIOS_HOST_CERT', 'value': '--cert'},
                            {'key': 'NAGIOS_HOST_KEY', 'value': '--key'},
                        ],
                        'dependency': [],
                        'flags': [],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver4.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': '0.1.7'
                }
            ]
        )

    def test_get_versions_of_metric_template_given_old_version_name(self):
        request = self.factory.get(self.url +
                                   'metrictemplate/argo.POEM-API-MON')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metrictemplate',
                             'argo.POEM-API-MON')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver5.id,
                    'object_repr':
                        'argo.POEM-API-MON-new [poem-probe-new (0.1.11)]',
                    'fields': {
                        'name': 'argo.POEM-API-MON-new',
                        'mtype': self.mtype1.name,
                        'probeversion': 'poem-probe-new (0.1.11)',
                        'parent': '',
                        'probeexecutable': 'poem-probe',
                        'config': [
                            {'key': 'maxCheckAttempts', 'value': '3'},
                            {'key': 'timeout', 'value': '60'},
                            {'key': 'path',
                             'value':
                                 '/usr/libexec/argo-monitoring/probes/argo'},
                            {'key': 'interval', 'value': '5'},
                            {'key': 'retryInterval', 'value': '5'}
                        ],
                        'attribute': [
                            {'key': 'POEM_PROFILE', 'value': '-r'},
                            {'key': 'NAGIOS_HOST_CERT', 'value': '--cert'},
                            {'key': 'NAGIOS_HOST_KEY', 'value': '--key'},
                        ],
                        'dependency': [],
                        'flags': [],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver5.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Changed name and probekey.',
                    'version': '0.1.11'
                },
                {
                    'id': self.ver4.id,
                    'object_repr':
                        'argo.POEM-API-MON [poem-probe (0.1.7)]',
                    'fields': {
                        'name': 'argo.POEM-API-MON',
                        'mtype': self.mtype1.name,
                        'probeversion': 'poem-probe (0.1.7)',
                        'parent': '',
                        'probeexecutable': 'poem-probe',
                        'config': [
                            {'key': 'maxCheckAttempts', 'value': '3'},
                            {'key': 'timeout', 'value': '60'},
                            {'key': 'path',
                             'value':
                                 '/usr/libexec/argo-monitoring/probes/argo'},
                            {'key': 'interval', 'value': '5'},
                            {'key': 'retryInterval', 'value': '5'}
                        ],
                        'attribute': [
                            {'key': 'POEM_PROFILE', 'value': '-r'},
                            {'key': 'NAGIOS_HOST_CERT', 'value': '--cert'},
                            {'key': 'NAGIOS_HOST_KEY', 'value': '--key'},
                        ],
                        'dependency': [],
                        'flags': [],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver4.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': '0.1.7'
                }
            ]
        )

    def test_get_versions_of_passive_metric_template(self):
        request = self.factory.get(self.url + 'org.apel.APEL-Pub-new')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metrictemplate', 'org.apel.APEL-Pub-new')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver7.id,
                    'object_repr':
                        'org.apel.APEL-Pub-new',
                    'fields': {
                        'name': 'org.apel.APEL-Pub-new',
                        'mtype': self.mtype2.name,
                        'probeversion': '',
                        'parent': '',
                        'probeexecutable': '',
                        'config': [],
                        'attribute': [],
                        'dependency': [],
                        'flags': [
                            {'key': 'OBSESS', 'value': '1'},
                            {'key': 'PASSIVE', 'value': '1'}
                        ],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver7.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Changed name.',
                    'version': datetime.datetime.strftime(
                        self.ver7.date_created, '%Y-%m-%d %H:%M:%S'
                    )
                },
                {
                    'id': self.ver6.id,
                    'object_repr':
                        'org.apel.APEL-Pub',
                    'fields': {
                        'name': 'org.apel.APEL-Pub',
                        'mtype': self.mtype2.name,
                        'probeversion': '',
                        'parent': '',
                        'probeexecutable': '',
                        'config': [],
                        'attribute': [],
                        'dependency': [],
                        'flags': [
                            {'key': 'OBSESS', 'value': '1'},
                            {'key': 'PASSIVE', 'value': '1'}
                        ],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver6.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': datetime.datetime.strftime(
                        self.ver6.date_created, '%Y-%m-%d %H:%M:%S'
                    )
                }
            ]
        )

    def test_get_nonexisting_probe_version(self):
        request = self.factory.get(self.url + 'probe/ams-probe')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'probe', 'ams-probe')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Version not found'})

    def test_get_all_probe_versions(self):
        request = self.factory.get(self.url + 'probe/')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'probe')
        self.assertEqual(
            [r for r in response.data],
            [
                'ams-publisher-probe (0.1.11)',
                'poem-probe (0.1.7)',
                'poem-probe-new (0.1.11)'
            ]
        )


class GetIsTenantSchemaAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.GetIsTenantSchema.as_view()
        self.url = '/api/v2/internal/istenantschema/'

    def test_get_tenant_schema(self):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {'isTenantSchema': True}
        )

    @patch('Poem.api.internal_views.app.connection')
    def test_get_schema_name_if_public_schema(self, args):
        args.schema_name = get_public_schema_name()
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {'isTenantSchema': False}
        )


class ListMetricTemplatesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricTemplates.as_view()
        self.url = '/api/v2/internal/metrictemplates/'
        self.user = CustUser.objects.create_user(username='testuser')

        self.mtype1 = admin_models.MetricTemplateType.objects.create(
            name='Active'
        )
        mtype2 = admin_models.MetricTemplateType.objects.create(name='Passive')

        self.mtype3 = poem_models.MetricType.objects.create(name='Active')
        mtype4 = poem_models.MetricType.objects.create(name='Passive')

        self.ct = ContentType.objects.get_for_model(poem_models.Metric)

        tag1 = admin_models.OSTag.objects.create(name='CentOS 6')
        tag2 = admin_models.OSTag.objects.create(name='CentOS 7')

        repo1 = admin_models.YumRepo.objects.create(name='repo-1', tag=tag1)
        repo2 = admin_models.YumRepo.objects.create(name='repo-2', tag=tag2)

        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo1)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.8'
        )
        package2.repos.add(repo1, repo2)

        package3 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        package3.repos.add(repo2)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        self.probeversion1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username,
        )

        probe1.package = package2
        probe1.comment = 'Newer version.'
        probe1.save()

        self.probeversion2 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='[{"changed": {"fields": ["package", "comment"]}}]',
            version_user=self.user.username
        )

        probe1.package = package3
        probe1.comment = 'Newest version.'
        probe1.save()

        self.probeversion3 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='[{"changed": {"fields": ["package", "comment"]}}]',
            version_user=self.user.username
        )

        for schema in [self.tenant.schema_name, get_public_schema_name()]:
            with schema_context(schema):
                if schema == get_public_schema_name():
                    Tenant.objects.create(name='public',
                                          domain_url='public',
                                          schema_name=get_public_schema_name())

        self.metrictemplate1 = admin_models.MetricTemplate.objects.create(
            name='argo.AMS-Check',
            mtype=self.mtype1,
            probekey=self.probeversion1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        self.metrictemplate2 = admin_models.MetricTemplate.objects.create(
            name='org.apel.APEL-Pub',
            flags='["OBSESS 1", "PASSIVE 1"]',
            mtype=mtype2,
        )

        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate1,
            name=self.metrictemplate1.name,
            mtype=self.metrictemplate1.mtype,
            probekey=self.metrictemplate1.probekey,
            probeexecutable=self.metrictemplate1.probeexecutable,
            config=self.metrictemplate1.config,
            attribute=self.metrictemplate1.attribute,
            dependency=self.metrictemplate1.dependency,
            flags=self.metrictemplate1.flags,
            files=self.metrictemplate1.files,
            parameter=self.metrictemplate1.parameter,
            fileparameter=self.metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Initial version.',
        )

        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate2,
            name=self.metrictemplate2.name,
            mtype=self.metrictemplate2.mtype,
            probekey=self.metrictemplate2.probekey,
            probeexecutable=self.metrictemplate2.probeexecutable,
            config=self.metrictemplate2.config,
            attribute=self.metrictemplate2.attribute,
            dependency=self.metrictemplate2.dependency,
            flags=self.metrictemplate2.flags,
            files=self.metrictemplate2.files,
            parameter=self.metrictemplate2.parameter,
            fileparameter=self.metrictemplate2.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Initial version.',
        )

        self.metrictemplate1.probekey = self.probeversion2
        self.metrictemplate1.config = '["maxCheckAttempts 4", "timeout 70", ' \
                                      '"path /usr/libexec/argo-monitoring/", ' \
                                      '"interval 5", "retryInterval 3"]'
        self.metrictemplate1.save()

        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate1,
            name=self.metrictemplate1.name,
            mtype=self.metrictemplate1.mtype,
            probekey=self.metrictemplate1.probekey,
            probeexecutable=self.metrictemplate1.probeexecutable,
            config=self.metrictemplate1.config,
            attribute=self.metrictemplate1.attribute,
            dependency=self.metrictemplate1.dependency,
            flags=self.metrictemplate1.flags,
            files=self.metrictemplate1.files,
            parameter=self.metrictemplate1.parameter,
            fileparameter=self.metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment=create_comment(self.metrictemplate1)
        )

        group = poem_models.GroupOfMetrics.objects.create(name='TEST')

        self.metric1 = poem_models.Metric.objects.create(
            name=self.metrictemplate1.name,
            group=group,
            mtype=self.mtype3,
            probekey=self.metrictemplate1.probekey,
            probeexecutable=self.metrictemplate1.probeexecutable,
            config=self.metrictemplate1.config,
            attribute=self.metrictemplate1.attribute,
            dependancy=self.metrictemplate1.dependency,
            flags=self.metrictemplate1.flags,
            files=self.metrictemplate1.files,
            parameter=self.metrictemplate1.parameter,
            fileparameter=self.metrictemplate1.fileparameter,
        )

        poem_models.TenantHistory.objects.create(
            object_id=self.metric1.id,
            object_repr=self.metric1.__str__(),
            serialized_data=serializers.serialize(
                'json', [self.metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            content_type=self.ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        self.metric2 = poem_models.Metric.objects.create(
            name=self.metrictemplate2.name,
            group=group,
            mtype=mtype4,
            probekey=self.metrictemplate2.probekey,
            probeexecutable=self.metrictemplate2.probeexecutable,
            config=self.metrictemplate2.config,
            attribute=self.metrictemplate2.attribute,
            dependancy=self.metrictemplate2.dependency,
            flags=self.metrictemplate2.flags,
            files=self.metrictemplate2.files,
            parameter=self.metrictemplate2.parameter,
            fileparameter=self.metrictemplate2.fileparameter,
        )

        poem_models.TenantHistory.objects.create(
            object_id=self.metric2.id,
            object_repr=self.metric2.__str__(),
            serialized_data=serializers.serialize(
                'json', [self.metric2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            content_type=self.ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

    def test_get_metric_template_list(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.metrictemplate1.id,
                    'name': 'argo.AMS-Check',
                    'mtype': 'Active',
                    'ostag': ['CentOS 6', 'CentOS 7'],
                    'probeversion': 'ams-probe (0.1.8)',
                    'parent': '',
                    'probeexecutable': 'ams-probe',
                    'config': [
                        {
                            'key': 'maxCheckAttempts',
                            'value': '4'
                        },
                        {
                            'key': 'timeout',
                            'value': '70'
                        },
                        {
                            'key': 'path',
                            'value': '/usr/libexec/argo-monitoring/'
                        },
                        {
                            'key': 'interval',
                            'value': '5'
                        },
                        {
                            'key': 'retryInterval',
                            'value': '3'
                        }
                    ],
                    'attribute': [
                        {
                            'key': 'argo.ams_TOKEN',
                            'value': '--token'
                        }
                    ],
                    'dependency': [],
                    'flags': [
                        {
                            'key': 'OBSESS',
                            'value': '1'
                        }
                    ],
                    'files': [],
                    'parameter': [
                        {
                            'key': '--project',
                            'value': 'EGI'
                        }
                    ],
                    'fileparameter': []
                },
                {
                    'id': self.metrictemplate2.id,
                    'name': 'org.apel.APEL-Pub',
                    'mtype': 'Passive',
                    'ostag': [],
                    'probeversion': '',
                    'parent': '',
                    'probeexecutable': '',
                    'config': [],
                    'attribute': [],
                    'dependency': [],
                    'flags': [
                        {
                            'key': 'OBSESS',
                            'value': '1'
                        },
                        {
                            'key': 'PASSIVE',
                            'value': '1'
                        }
                    ],
                    'files': [],
                    'parameter': [],
                    'fileparameter': []
                }
            ]
        )

    def test_get_metrictemplate_by_name(self):
        request = self.factory.get(self.url + 'argo.AMS-Check')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'argo.AMS-Check')
        self.assertEqual(
            response.data,
            {
                'id': self.metrictemplate1.id,
                'name': 'argo.AMS-Check',
                'mtype': 'Active',
                'probeversion': 'ams-probe (0.1.8)',
                'parent': '',
                'probeexecutable': 'ams-probe',
                'config': [
                    {
                        'key': 'maxCheckAttempts',
                        'value': '4'
                    },
                    {
                        'key': 'timeout',
                        'value': '70'
                    },
                    {
                        'key': 'path',
                        'value': '/usr/libexec/argo-monitoring/'
                    },
                    {
                        'key': 'interval',
                        'value': '5'
                    },
                    {
                        'key': 'retryInterval',
                        'value': '3'
                    }
                ],
                'attribute': [
                    {
                        'key': 'argo.ams_TOKEN',
                        'value': '--token'
                    }
                ],
                'dependency': [],
                'flags': [
                    {
                        'key': 'OBSESS',
                        'value': '1'
                    }
                ],
                'files': [],
                'parameter': [
                    {
                        'key': '--project',
                        'value': 'EGI'
                    }
                ],
                'fileparameter': []
            }
        )

    def test_get_metric_template_by_nonexisting_name(self):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Metric template not found'})

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_post_metric_template(self, func):
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path',
             'value': '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        data = {
            'cloned_from': '',
            'name': 'new-template',
            'probeversion': 'ams-probe (0.1.7)',
            'mtype': 'Active',
            'probeexecutable': 'ams-probe',
            'parent': '',
            'config': json.dumps(conf),
            'attribute': json.dumps([{'key': 'attr-key', 'value': 'attr-val'}]),
            'dependency': json.dumps([{'key': 'dep-key', 'value': 'dep-val'}]),
            'parameter': json.dumps([{'key': 'par-key', 'value': 'par-val'}]),
            'flags': json.dumps([{'key': 'flag-key', 'value': 'flag-val'}]),
            'files': json.dumps([{'key': 'file-key', 'value': 'file-val'}]),
            'fileparameter': json.dumps([{'key': 'fp-key', 'value': 'fp-val'}])
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mt = admin_models.MetricTemplate.objects.get(name='new-template')
        versions = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        )
        self.assertEqual(versions.count(), 1)
        self.assertEqual(mt.mtype, self.mtype1)
        self.assertEqual(mt.probekey, self.probeversion1)
        self.assertEqual(mt.parent, '')
        self.assertEqual(mt.probeexecutable, '["ams-probe"]')
        self.assertEqual(
            mt.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 6", "retryInterval 4"]'
        )
        self.assertEqual(mt.attribute, '["attr-key attr-val"]')
        self.assertEqual(mt.dependency, '["dep-key dep-val"]')
        self.assertEqual(mt.flags, '["flag-key flag-val"]')
        self.assertEqual(mt.files, '["file-key file-val"]')
        self.assertEqual(mt.parameter, '["par-key par-val"]')
        self.assertEqual(mt.fileparameter, '["fp-key fp-val"]')
        self.assertEqual(versions[0].name, mt.name)
        self.assertEqual(versions[0].mtype, mt.mtype)
        self.assertEqual(
            versions[0].probekey, mt.probekey
        )
        self.assertEqual(versions[0].parent, mt.parent)
        self.assertEqual(versions[0].probeexecutable, mt.probeexecutable)
        self.assertEqual(versions[0].config, mt.config)
        self.assertEqual(versions[0].attribute, mt.attribute)
        self.assertEqual(versions[0].dependency, mt.dependency)
        self.assertEqual(versions[0].flags, mt.flags)
        self.assertEqual(versions[0].files, mt.files)
        self.assertEqual(versions[0].parameter, mt.parameter)
        self.assertEqual(versions[0].fileparameter, mt.fileparameter)
        self.assertEqual(versions[0].version_user, 'testuser')
        self.assertEqual(versions[0].version_comment, 'Initial version.')

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_post_metric_template_with_existing_name(self, func):
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path',
             'value': '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        data = {
            'name': 'argo.AMS-Check',
            'probeversion': 'ams-probe (0.1.7)',
            'mtype': 'Active',
            'probeexecutable': 'ams-probe',
            'parent': '',
            'config': json.dumps(conf),
            'attribute': json.dumps([{'key': '', 'value': ''}]),
            'dependency': json.dumps([{'key': '', 'value': ''}]),
            'parameter': json.dumps([{'key': '', 'value': ''}]),
            'flags': json.dumps([{'key': '', 'value': ''}]),
            'files': json.dumps([{'key': '', 'value': ''}]),
            'fileparameter': json.dumps([{'key': '', 'value': ''}])
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                'detail': 'Metric template with this name already exists.'
            }
        )

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_metrictemplate_without_changing_probekey(self, func):
        attr = [
            {'key': 'argo.ams_TOKEN2', 'value': '--token'}
        ]
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path', 'value':
                '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        data = {
            'id': self.metrictemplate1.id,
            'name': 'argo.AMS-Check-new',
            'mtype': 'Active',
            'probeversion': 'ams-probe (0.1.8)',
            'parent': 'argo.AMS-Check',
            'probeexecutable': 'ams-probe',
            'config': json.dumps(conf),
            'attribute': json.dumps(attr),
            'dependency': json.dumps([{'key': 'dep-key', 'value': 'dep-val'}]),
            'parameter': json.dumps([{'key': 'par-key', 'value': 'par-val'}]),
            'flags': json.dumps([{'key': 'flag-key', 'value': 'flag-val'}]),
            'files': json.dumps([{'key': 'file-key', 'value': 'file-val'}]),
            'fileparameter': json.dumps([{'key': 'fp-key', 'value': 'fp-val'}])
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mt = admin_models.MetricTemplate.objects.get(id=self.metrictemplate1.id)
        metric = poem_models.Metric.objects.get(id=self.metric1.id)
        versions = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        ).order_by('-date_created')
        metric_versions = poem_models.TenantHistory.objects.filter(
            object_id=metric.id, content_type=self.ct
        )

        serialized_data = json.loads(
            metric_versions[0].serialized_data
        )[0]['fields']
        self.assertEqual(versions.count(), 2)
        self.assertEqual(versions[1].version_comment, 'Initial version.')
        comment_set = set()
        for item in json.loads(versions[0].version_comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["config"], '
                '"object": ["interval", "maxCheckAttempts", "retryInterval", '
                '"timeout"]}}',
                '{"deleted": {"fields": ["attribute"], '
                '"object": ["argo.ams_TOKEN"]}}',
                '{"added": {"fields": ["attribute"], '
                '"object": ["argo.ams_TOKEN2"]}}',
                '{"added": {"fields": ["dependency"], "object": ["dep-key"]}}',
                '{"deleted": {"fields": ["flags"], "object": ["OBSESS"]}}',
                '{"added": {"fields": ["flags"], "object": ["flag-key"]}}',
                '{"added": {"fields": ["files"], "object": ["file-key"]}}',
                '{"deleted": {"fields": ["parameter"], '
                '"object": ["--project"]}}',
                '{"added": {"fields": ["parameter"], "object": ["par-key"]}}',
                '{"added": {"fields": ["fileparameter"], '
                '"object": ["fp-key"]}}',
                '{"added": {"fields": ["parent"]}}',
                '{"changed": {"fields": ["name", "probekey"]}}'
            }
        )
        self.assertEqual(metric_versions.count(), 1)
        self.assertEqual(mt.name, 'argo.AMS-Check-new')
        self.assertEqual(mt.mtype.name, 'Active')
        self.assertEqual(mt.parent, '["argo.AMS-Check"]')
        self.assertEqual(mt.probeexecutable, '["ams-probe"]')
        self.assertEqual(
            mt.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 6", "retryInterval 4"]'
        )
        self.assertEqual(mt.attribute, '["argo.ams_TOKEN2 --token"]')
        self.assertEqual(mt.dependency, '["dep-key dep-val"]')
        self.assertEqual(mt.flags, '["flag-key flag-val"]')
        self.assertEqual(mt.files, '["file-key file-val"]')
        self.assertEqual(mt.parameter, '["par-key par-val"]')
        self.assertEqual(mt.fileparameter, '["fp-key fp-val"]')
        self.assertEqual(versions[0].name, mt.name)
        self.assertEqual(versions[0].mtype, mt.mtype)
        self.assertEqual(versions[0].probekey, mt.probekey)
        self.assertEqual(versions[0].parent, mt.parent)
        self.assertEqual(versions[0].probeexecutable, mt.probeexecutable)
        self.assertEqual(versions[0].config, mt.config)
        self.assertEqual(versions[0].attribute, mt.attribute)
        self.assertEqual(versions[0].dependency, mt.dependency)
        self.assertEqual(versions[0].flags, mt.flags)
        self.assertEqual(versions[0].files, mt.files)
        self.assertEqual(versions[0].parameter, mt.parameter)
        self.assertEqual(versions[0].fileparameter, mt.fileparameter)
        self.assertEqual(metric.name, mt.name)
        self.assertEqual(metric.mtype.name, mt.mtype.name)
        self.assertEqual(metric.probekey, mt.probekey)
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, mt.parent)
        self.assertEqual(metric.probeexecutable, mt.probeexecutable)
        for item in json.loads(metric.config):
            if item.startswith('path'):
                metric_path = item.split(' ')[1]
        for item in json.loads(mt.config):
            if item.startswith('path'):
                mt_path = item.split(' ')[1]
        self.assertEqual(metric_path, mt_path)
        self.assertEqual(metric.attribute, mt.attribute)
        self.assertEqual(metric.dependancy, mt.dependency)
        self.assertEqual(metric.flags, mt.flags)
        self.assertEqual(metric.files, mt.files)
        self.assertEqual(metric.parameter, mt.parameter)
        self.assertEqual(metric.fileparameter, mt.fileparameter)
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], [metric.mtype.name])
        self.assertEqual(
            serialized_data['probekey'],
            [metric.probekey.name, metric.probekey.package.version]
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_metrictemplate_with_new_probekey(self, func):
        attr = [
            {'key': 'argo.ams_TOKEN2', 'value': '--token'}
        ]
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path', 'value':
                '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        data = {
            'id': self.metrictemplate1.id,
            'name': 'argo.AMS-Check-new',
            'mtype': 'Active',
            'probeversion': 'ams-probe (0.1.11)',
            'parent': 'argo.AMS-Check',
            'probeexecutable': 'ams-probe-new',
            'config': json.dumps(conf),
            'attribute': json.dumps(attr),
            'dependency': json.dumps([{'key': 'dep-key', 'value': 'dep-val'}]),
            'parameter': json.dumps([{'key': 'par-key', 'value': 'par-val'}]),
            'flags': json.dumps([{'key': 'flag-key', 'value': 'flag-val'}]),
            'files': json.dumps([{'key': 'file-key', 'value': 'file-val'}]),
            'fileparameter': json.dumps([{'key': 'fp-key', 'value': 'fp-val'}])
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        metric = poem_models.Metric.objects.get(id=self.metric1.id)
        mt = admin_models.MetricTemplate.objects.get(id=self.metrictemplate1.id)
        versions = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        )
        metric_versions = poem_models.TenantHistory.objects.filter(
            object_id=metric.id, content_type=self.ct
        )
        serialized_data = json.loads(
            metric_versions[0].serialized_data
        )[0]['fields']
        self.assertEqual(versions.count(), 3)
        comment_set = set()
        for item in json.loads(versions[0].version_comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["config"], '
                '"object": ["interval", "path", "retryInterval"]}}',
                '{"deleted": {"fields": ["attribute"], '
                '"object": ["argo.ams_TOKEN"]}}',
                '{"added": {"fields": ["attribute"], '
                '"object": ["argo.ams_TOKEN2"]}}',
                '{"added": {"fields": ["dependency"], "object": ["dep-key"]}}',
                '{"deleted": {"fields": ["flags"], "object": ["OBSESS"]}}',
                '{"added": {"fields": ["flags"], "object": ["flag-key"]}}',
                '{"added": {"fields": ["files"], "object": ["file-key"]}}',
                '{"deleted": {"fields": ["parameter"], '
                '"object": ["--project"]}}',
                '{"added": {"fields": ["parameter"], "object": ["par-key"]}}',
                '{"added": {"fields": ["fileparameter"], '
                '"object": ["fp-key"]}}',
                '{"added": {"fields": ["parent"]}}',
                '{"changed": {"fields": ["name", "probeexecutable", '
                '"probekey"]}}'
            }
        )
        self.assertEqual(metric_versions.count(), 1)
        self.assertEqual(mt.name, 'argo.AMS-Check-new')
        self.assertEqual(mt.mtype.name, 'Active')
        self.assertEqual(mt.probeexecutable, '["ams-probe-new"]')
        self.assertEqual(mt.parent, '["argo.AMS-Check"]')
        self.assertEqual(
            mt.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring/probes/argo", '
            '"interval 6", "retryInterval 4"]'
        )
        self.assertEqual(mt.attribute, '["argo.ams_TOKEN2 --token"]')
        self.assertEqual(mt.dependency, '["dep-key dep-val"]')
        self.assertEqual(mt.flags, '["flag-key flag-val"]')
        self.assertEqual(mt.files, '["file-key file-val"]')
        self.assertEqual(mt.parameter, '["par-key par-val"]')
        self.assertEqual(mt.fileparameter, '["fp-key fp-val"]')
        self.assertEqual(versions[0].name, mt.name)
        self.assertEqual(versions[0].mtype, mt.mtype)
        self.assertEqual(versions[0].probekey, mt.probekey)
        self.assertEqual(versions[0].parent, mt.parent)
        self.assertEqual(versions[0].probeexecutable, mt.probeexecutable)
        self.assertEqual(versions[0].config, mt.config)
        self.assertEqual(versions[0].attribute, mt.attribute)
        self.assertEqual(versions[0].dependency, mt.dependency)
        self.assertEqual(versions[0].flags, mt.flags)
        self.assertEqual(versions[0].files, mt.files)
        self.assertEqual(versions[0].parameter, mt.parameter)
        self.assertEqual(versions[0].fileparameter, mt.fileparameter)
        self.assertEqual(metric.name, 'argo.AMS-Check')
        self.assertEqual(metric.mtype.name, 'Active')
        self.assertEqual(metric.probekey, self.probeversion2)
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["ams-probe"]')
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring/", '
            '"interval 5", "retryInterval 3"]'
        )
        self.assertEqual(metric.attribute, '["argo.ams_TOKEN --token"]')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '["--project EGI"]')
        self.assertEqual(metric.fileparameter, '')
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], [metric.mtype.name])
        self.assertEqual(
            serialized_data['probekey'],
            [metric.probekey.name, metric.probekey.package.version]
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_passive_metric_template(self, func):
        data = {
            'id': self.metrictemplate2.id,
            'name': 'org.apel.APEL-Pub-new',
            'probeversion': '',
            'mtype': 'Passive',
            'probeexecutable': '',
            'parent': '',
            'config': json.dumps([{'key': '', 'value': ''}]),
            'attribute': json.dumps([{'key': '', 'value': ''}]),
            'dependency': json.dumps([{'key': '', 'value': ''}]),
            'parameter': json.dumps([{'key': '', 'value': ''}]),
            'flags': json.dumps([{'key': 'PASSIVE', 'value': '1'}]),
            'files': json.dumps([{'key': '', 'value': ''}]),
            'fileparameter': json.dumps([{'key': '', 'value': ''}]),
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        metric = poem_models.Metric.objects.get(id=self.metric2.id)
        mt = admin_models.MetricTemplate.objects.get(id=self.metrictemplate2.id)
        versions = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        )
        metric_versions = poem_models.TenantHistory.objects.filter(
            object_id=metric.id, content_type=self.ct
        )
        serialized_data = json.loads(
            metric_versions[0].serialized_data
        )[0]['fields']
        self.assertEqual(versions.count(), 1)
        self.assertEqual(metric_versions.count(), 1)
        self.assertEqual(mt.name, 'org.apel.APEL-Pub-new')
        self.assertEqual(mt.mtype.name, 'Passive')
        self.assertEqual(mt.probeexecutable, '')
        self.assertEqual(mt.parent, '')
        self.assertEqual(mt.config, '')
        self.assertEqual(mt.attribute, '')
        self.assertEqual(mt.dependency, '')
        self.assertEqual(mt.flags, '["PASSIVE 1"]')
        self.assertEqual(mt.files, '')
        self.assertEqual(mt.parameter, '')
        self.assertEqual(mt.fileparameter, '')
        self.assertEqual(versions[0].name, mt.name)
        self.assertEqual(versions[0].mtype, mt.mtype)
        self.assertEqual(versions[0].probekey, mt.probekey)
        self.assertEqual(versions[0].parent, mt.parent)
        self.assertEqual(versions[0].probeexecutable, mt.probeexecutable)
        self.assertEqual(versions[0].config, mt.config)
        self.assertEqual(versions[0].attribute, mt.attribute)
        self.assertEqual(versions[0].dependency, mt.dependency)
        self.assertEqual(versions[0].flags, mt.flags)
        self.assertEqual(versions[0].files, mt.files)
        self.assertEqual(versions[0].parameter, mt.parameter)
        self.assertEqual(versions[0].fileparameter, mt.fileparameter)
        self.assertEqual(metric.name, mt.name)
        self.assertEqual(metric.mtype.name, mt.mtype.name)
        self.assertEqual(metric.probekey, mt.probekey)
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, mt.parent)
        self.assertEqual(metric.probeexecutable, mt.probeexecutable)
        self.assertEqual(metric.config, mt.config)
        self.assertEqual(metric.attribute, mt.attribute)
        self.assertEqual(metric.dependancy, mt.dependency)
        self.assertEqual(metric.flags, mt.flags)
        self.assertEqual(metric.files, mt.files)
        self.assertEqual(metric.parameter, mt.parameter)
        self.assertEqual(metric.fileparameter, mt.fileparameter)
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], [metric.mtype.name])
        self.assertEqual(serialized_data['probekey'], None)
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_metrictemplate_without_updating_older_version_metric(self, f):
        self.metrictemplate1.probekey = self.probeversion3
        self.metrictemplate1.save()
        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.metrictemplate1,
            name=self.metrictemplate1.name,
            mtype=self.metrictemplate1.mtype,
            probekey=self.metrictemplate1.probekey,
            probeexecutable=self.metrictemplate1.probeexecutable,
            attribute=self.metrictemplate1.attribute,
            dependency=self.metrictemplate1.dependency,
            flags=self.metrictemplate1.flags,
            files=self.metrictemplate1.files,
            parameter=self.metrictemplate1.parameter,
            fileparameter=self.metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment=create_comment(self.metrictemplate1)
        )
        attr = [
            {'key': 'argo.ams_TOKEN2', 'value': '--token'}
        ]
        conf = [
            {'key': 'maxCheckAttempts', 'value': '4'},
            {'key': 'timeout', 'value': '70'},
            {'key': 'path', 'value':
                '/usr/libexec/argo-monitoring2/probes/argo'},
            {'key': 'interval', 'value': '6'},
            {'key': 'retryInterval', 'value': '4'}
        ]
        data = {
            'id': self.metrictemplate1.id,
            'name': 'argo.AMS-Check-new',
            'mtype': 'Active',
            'probeversion': 'ams-probe (0.1.11)',
            'parent': 'argo.AMS-Check',
            'probeexecutable': 'ams-probe',
            'config': json.dumps(conf),
            'attribute': json.dumps(attr),
            'dependency': json.dumps([{'key': 'dep-key', 'value': 'dep-val'}]),
            'parameter': json.dumps([{'key': 'par-key', 'value': 'par-val'}]),
            'flags': json.dumps([{'key': 'flag-key', 'value': 'flag-val'}]),
            'files': json.dumps([{'key': 'file-key', 'value': 'file-val'}]),
            'fileparameter': json.dumps([{'key': 'fp-key', 'value': 'fp-val'}])
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mt = admin_models.MetricTemplate.objects.get(id=self.metrictemplate1.id)
        metric = poem_models.Metric.objects.get(id=self.metric1.id)
        versions = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        )
        metric_versions = poem_models.TenantHistory.objects.filter(
            object_id=metric.id, content_type=self.ct
        )
        serialized_data = json.loads(
            metric_versions[0].serialized_data
        )[0]['fields']
        self.assertEqual(versions.count(), 3)
        self.assertEqual(metric_versions.count(), 1)
        self.assertEqual(mt.name, 'argo.AMS-Check-new')
        self.assertEqual(mt.mtype.name, 'Active')
        self.assertEqual(mt.parent, '["argo.AMS-Check"]')
        self.assertEqual(mt.probeexecutable, '["ams-probe"]')
        self.assertEqual(
            mt.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring2/probes/argo", '
            '"interval 6", "retryInterval 4"]'
        )
        self.assertEqual(mt.attribute, '["argo.ams_TOKEN2 --token"]')
        self.assertEqual(mt.dependency, '["dep-key dep-val"]')
        self.assertEqual(mt.flags, '["flag-key flag-val"]')
        self.assertEqual(mt.files, '["file-key file-val"]')
        self.assertEqual(mt.parameter, '["par-key par-val"]')
        self.assertEqual(mt.fileparameter, '["fp-key fp-val"]')
        self.assertEqual(versions[0].name, mt.name)
        self.assertEqual(versions[0].mtype, mt.mtype)
        self.assertEqual(versions[0].probekey, mt.probekey)
        self.assertEqual(versions[0].parent, mt.parent)
        self.assertEqual(versions[0].probeexecutable, mt.probeexecutable)
        self.assertEqual(versions[0].config, mt.config)
        self.assertEqual(versions[0].attribute, mt.attribute)
        self.assertEqual(versions[0].dependency, mt.dependency)
        self.assertEqual(versions[0].flags, mt.flags)
        self.assertEqual(versions[0].files, mt.files)
        self.assertEqual(versions[0].parameter, mt.parameter)
        self.assertEqual(versions[0].fileparameter, mt.fileparameter)
        self.assertEqual(metric.name, 'argo.AMS-Check')
        self.assertEqual(metric.mtype.name, 'Active')
        self.assertEqual(metric.probekey, self.probeversion2)
        self.assertEqual(metric.group.name, 'TEST')
        self.assertEqual(metric.parent, '')
        self.assertEqual(metric.probeexecutable, '["ams-probe"]')
        self.assertEqual(
            metric.config,
            '["maxCheckAttempts 4", "timeout 70", '
            '"path /usr/libexec/argo-monitoring/", '
            '"interval 5", "retryInterval 3"]'
        )
        self.assertEqual(metric.attribute, '["argo.ams_TOKEN --token"]')
        self.assertEqual(metric.dependancy, '')
        self.assertEqual(metric.flags, '["OBSESS 1"]')
        self.assertEqual(metric.files, '')
        self.assertEqual(metric.parameter, '["--project EGI"]')
        self.assertEqual(metric.fileparameter, '')
        self.assertEqual(serialized_data['name'], metric.name)
        self.assertEqual(serialized_data['mtype'], [metric.mtype.name])
        self.assertEqual(
            serialized_data['probekey'],
            [metric.probekey.name, metric.probekey.package.version]
        )
        self.assertEqual(serialized_data['group'], ['TEST'])
        self.assertEqual(serialized_data['parent'], metric.parent)
        self.assertEqual(
            serialized_data['probeexecutable'], metric.probeexecutable
        )
        self.assertEqual(serialized_data['config'], metric.config)
        self.assertEqual(serialized_data['attribute'], metric.attribute)
        self.assertEqual(serialized_data['dependancy'], metric.dependancy)
        self.assertEqual(serialized_data['flags'], metric.flags)
        self.assertEqual(serialized_data['files'], metric.files)
        self.assertEqual(serialized_data['parameter'], metric.parameter)
        self.assertEqual(serialized_data['fileparameter'], metric.fileparameter)

    @patch('Poem.api.internal_views.metrictemplates.inline_metric_for_db',
           side_effect=mocked_inline_metric_for_db)
    def test_put_metrictemplate_with_existing_name(self, func):
        attr = [
            {'key': 'argo.ams_TOKEN', 'value': '--token'}
        ]
        conf = [
            {'key': 'maxCheckAttempts', 'value': '3'},
            {'key': 'timeout', 'value': '60'},
            {'key': 'path', 'value':
                '/usr/libexec/argo-monitoring/probes/argo'},
            {'key': 'interval', 'value': '5'},
            {'key': 'retryInterval', 'value': '3'}
        ]
        data = {
            'id': self.metrictemplate1.id,
            'name': 'org.apel.APEL-Pub',
            'mtype': self.mtype1,
            'probeversion': 'ams-probe (0.1.7)',
            'parent': '',
            'probeexecutable': 'ams-probe',
            'config': json.dumps(conf),
            'attribute': json.dumps(attr),
            'dependency': json.dumps([{'key': 'dep-key', 'value': 'dep-val'}]),
            'parameter': json.dumps([{'key': 'par-key', 'value': 'par-val'}]),
            'flags': json.dumps([{'key': 'flag-key', 'value': 'flag-val'}]),
            'files': json.dumps([{'key': 'file-key', 'value': 'file-val'}]),
            'fileparameter': json.dumps([{'key': 'fp-key', 'value': 'fp-val'}])
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Metric template with this name already exists.'}
        )

    def test_delete_metric_template(self):
        self.assertEqual(admin_models.MetricTemplate.objects.all().count(), 2)
        request = self.factory.delete(self.url + 'argo.AMS-Check')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'argo.AMS-Check')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(admin_models.MetricTemplate.objects.all().count(), 1)

    def test_delete_nonexisting_metric_template(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_metric_template_without_specifying_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListMetricTemplateTypesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricTemplateTypes.as_view()
        self.url = '/api/v2/internal/mttypes/'
        self.user = CustUser.objects.create_user(username='testuser')

        admin_models.MetricTemplateType.objects.create(name='Active')
        admin_models.MetricTemplateType.objects.create(name='Passive')

    def test_get_metric_template_types(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            [r for r in response.data],
            [
                'Active',
                'Passive'
            ]
        )


class ImportMetricsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ImportMetrics.as_view()
        self.url = '/api/v2/internal/importmetrics/'
        self.user = CustUser.objects.create_user(username='testuser')

        mt = admin_models.MetricTemplateType.objects.create(name='Active')
        poem_models.MetricType.objects.create(name='Active')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)

        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        package2.repos.add(repo)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service.',
            comment='Initial version',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        probe2 = admin_models.Probe.objects.create(
            name='ams-publisher-probe',
            package=package2,
            description='Probe is inspecting AMS publisher running on Nagios '
                        'monitoring instances.',
            comment='New version',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        pk1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        pk2 = admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        self.defaultGroup = poem_models.GroupOfMetrics.objects.create(
            name='TENANT'
        )

        self.template1 = admin_models.MetricTemplate.objects.create(
            name='argo.AMS-Check',
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]',
            mtype=mt,
            probekey=pk1
        )

        self.template2 = admin_models.MetricTemplate.objects.create(
            name='argo.AMSPublisher-Check',
            probeexecutable='["ams-publisher-probe"]',
            config='["interval 180", "maxCheckAttempts 1", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"retryInterval 1", "timeout 120"]',
            flags='["NOHOSTNAME 1", "NOTIMEOUT 1"]',
            parameter='["-s /var/run/argo-nagios-ams-publisher/sock", '
                      '"-c 4000"]',
            mtype=mt,
            probekey=pk2
        )

    @patch('Poem.poem.dbmodels.metricstags.GroupOfMetrics.objects.get')
    def test_import_metrics(self, gm):
        gm.return_value = self.defaultGroup
        self.assertEqual(poem_models.Metric.objects.all().count(), 0)
        data = {
            'metrictemplates': ['argo.AMS-Check', 'argo.AMSPublisher-Check']
        }
        request = self.factory.post(self.url, data, format='json')
        request.tenant = self.tenant
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(poem_models.Metric.objects.all().count(), 2)
        mt1 = poem_models.Metric.objects.get(name='argo.AMS-Check')
        mt2 = poem_models.Metric.objects.get(name='argo.AMSPublisher-Check')
        self.assertEqual(mt1.parent, self.template1.parent)
        self.assertEqual(mt1.probeexecutable, self.template1.probeexecutable)
        self.assertEqual(mt1.config, self.template1.config)
        self.assertEqual(mt1.attribute, self.template1.attribute)
        self.assertEqual(mt1.dependancy, self.template1.dependency)
        self.assertEqual(mt1.flags, self.template1.flags)
        self.assertEqual(mt1.files, self.template1.files)
        self.assertEqual(mt1.parameter, self.template1.parameter)
        self.assertEqual(mt1.fileparameter, self.template1.fileparameter)
        self.assertEqual(mt1.probekey, self.template1.probekey)
        self.assertEqual(mt2.parent, self.template2.parent)
        self.assertEqual(mt2.probeexecutable, self.template2.probeexecutable)
        self.assertEqual(mt2.config, self.template2.config)
        self.assertEqual(mt2.attribute, self.template2.attribute)
        self.assertEqual(mt2.dependancy, self.template2.dependency)
        self.assertEqual(mt2.flags, self.template2.flags)
        self.assertEqual(mt2.files, self.template2.files)
        self.assertEqual(mt2.parameter, self.template2.parameter)
        self.assertEqual(mt2.fileparameter, self.template2.fileparameter)
        self.assertEqual(mt2.probekey, self.template2.probekey)


class ListMetricTemplatesForProbeVersionAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricTemplatesForProbeVersion.as_view()
        self.url = '/api/v2/internal/metricsforprobes/'
        self.user = CustUser.objects.create_user(username='testuser')

        mtype1 = admin_models.MetricTemplateType.objects.create(name='Active')
        mtype2 = admin_models.MetricTemplateType.objects.create(name='Passive')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)
        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        self.probeversion1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        admin_models.MetricTemplate.objects.create(
            name='argo.AMS-Check',
            mtype=mtype1,
            probekey=self.probeversion1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        admin_models.MetricTemplate.objects.create(
            name='org.apel.APEL-Pub',
            flags='["OBSESS 1", "PASSIVE 1"]',
            mtype=mtype2,
        )

        admin_models.MetricTemplate.objects.create(
            name='test-metric',
            mtype=mtype1,
            probekey=self.probeversion1,
            probeexecutable='["test-metric"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

    def test_get_metric_templates_for_probe_version(self):
        request = self.factory.get(self.url + 'ams-probe(0.1.7)')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'ams-probe(0.1.7)')
        self.assertEqual(
            [r for r in response.data],
            ['argo.AMS-Check', 'test-metric']
        )


class ListTenantVersionsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListTenantVersions.as_view()
        self.url = '/api/v2/internal/tenantversion/'
        self.user = CustUser.objects.create_user(username='testuser')

        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)
        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        package2.repos.add(repo)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        ct_m = ContentType.objects.get_for_model(poem_models.Metric)
        ct_mp = ContentType.objects.get_for_model(poem_models.MetricProfiles)
        ct_aggr = ContentType.objects.get_for_model(poem_models.Aggregation)
        ct_tp = ContentType.objects.get_for_model(
            poem_models.ThresholdsProfiles
        )

        self.probever1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probe1.package = package2
        probe1.save()

        self.probever2 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Changed package.',
            version_user=self.user.username
        )

        self.mtype1 = poem_models.MetricType.objects.create(name='Active')
        self.mtype2 = poem_models.MetricType.objects.create(name='Passive')

        group1 = poem_models.GroupOfMetrics.objects.create(name='EGI')
        group2 = poem_models.GroupOfMetrics.objects.create(name='TEST')

        poem_models.GroupOfMetricProfiles.objects.create(name='EGI')
        poem_models.GroupOfMetricProfiles.objects.create(name='NEW_GROUP')

        self.metric1 = poem_models.Metric.objects.create(
            name='argo.AMS-Check',
            mtype=self.mtype1,
            group=group1,
            probekey=self.probever1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        poem_models.Metric.objects.create(
            name='test.AMS-Check',
            mtype=self.mtype1,
            group=group1,
            probekey=self.probever1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path /usr/libexec/argo-monitoring/probes/argo",'
                   ' "interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        self.ver1 = poem_models.TenantHistory.objects.create(
            object_id=self.metric1.id,
            serialized_data=serializers.serialize(
                'json', [self.metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr='argo.AMS-Check',
            content_type=ct_m,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        self.metric1.name = 'argo.AMS-Check-new'
        self.metric1.probeexecutable = '["ams-probe-2"]'
        self.metric1.probekey = self.probever2
        self.metric1.group = group2
        self.metric1.parent = '["new-parent"]'
        self.metric1.config = '["maxCheckAttempts 4", "timeout 70", ' \
                              '"path /usr/libexec/argo-monitoring/' \
                              'probes/argo2", "interval 5", "retryInterval 4"]'
        self.metric1.attribute = '["argo.ams_TOKEN2 --token"]'
        self.metric1.dependancy = '["new-key new-value"]'
        self.metric1.flags = ''
        self.metric1.parameter = ''
        self.metric1.fileparameter = '["new-key new-value"]'
        self.metric1.save()

        comment = create_comment(
            self.metric1, ct=ct_m, new_serialized_data=serializers.serialize(
                'json', [self.metric1], use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        self.ver2 = poem_models.TenantHistory.objects.create(
            object_id=self.metric1.id,
            serialized_data=serializers.serialize(
                'json', [self.metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric1.__str__(),
            content_type=ct_m,
            date_created=datetime.datetime.now(),
            comment=comment,
            user=self.user.username
        )

        self.metric2 = poem_models.Metric.objects.create(
            name='org.apel.APEL-Pub',
            mtype=self.mtype2,
            group=group1,
            flags='["OBSESS 1", "PASSIVE 1"]'
        )

        self.ver3 = poem_models.TenantHistory.objects.create(
            object_id=self.metric2.id,
            serialized_data=serializers.serialize(
                'json', [self.metric2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric2.__str__(),
            content_type=ct_m,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

        self.mp1 = poem_models.MetricProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.mp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]["fields"].update({
            "metricinstances": [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['APEL', 'org.apel.APEL-Sync']
            ]
        })

        self.ver4 = poem_models.TenantHistory.objects.create(
            object_id=self.mp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.mp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=ct_mp
        )

        self.mp1.groupname = 'NEW_GROUP'
        self.mp1.name = 'TEST_PROFILE2'
        self.mp1.save()

        data = json.loads(
            serializers.serialize(
                'json', [self.mp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]["fields"].update({
            "metricinstances": [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
            ]
        })

        comment = create_comment(
            self.mp1, ct=ct_mp, new_serialized_data=json.dumps(data)
        )

        self.ver5 = poem_models.TenantHistory.objects.create(
            object_id=self.mp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.mp1.__str__(),
            comment=comment,
            user='testuser',
            content_type=ct_mp
        )

        self.aggr1 = poem_models.Aggregation.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.aggr1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'endpoint_group': 'sites',
            'metric_operation': 'AND',
            'profile_operation': 'AND',
            'metric_profile': 'TEST_PROFILE',
            'groups': [
                {
                    'name': 'Group1',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                },
                {
                    'name': 'Group2',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'VOMS',
                            'operation': 'OR'
                        },
                        {
                            'name': 'argo.api',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })

        self.ver6 = poem_models.TenantHistory.objects.create(
            object_id=self.aggr1.id,
            serialized_data=json.dumps(data),
            object_repr=self.aggr1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=ct_aggr
        )

        self.aggr1.name = 'TEST_PROFILE2'
        self.aggr1.groupname = 'TEST2'
        self.aggr1.save()

        data = json.loads(
            serializers.serialize(
                'json', [self.aggr1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'endpoint_group': 'servicegroups',
            'metric_operation': 'OR',
            'profile_operation': 'OR',
            'metric_profile': 'TEST_PROFILE2',
            'groups': [
                {
                    'name': 'Group1a',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                },
                {
                    'name': 'Group2',
                    'operation': 'OR',
                    'services': [
                        {
                            'name': 'argo.api',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })

        self.ver7 = poem_models.TenantHistory.objects.create(
            object_id=self.aggr1.id,
            serialized_data=json.dumps(data),
            object_repr=self.aggr1.__str__(),
            comment='[{"changed": {"fields": ["endpoint_group", "groupname", '
                    '"metric_operation", "metric_profile", "name", '
                    '"profile_operation"]}}, {"deleted": {"fields": '
                    '["groups"], "object": ["Group1"]}}, {"added": {"fields": '
                    '["groups"], "object": ["Group1a"]}}, {"changed": '
                    '{"fields": ["groups"], "object": ["Group2"]}}]',
            user='testuser',
            content_type=ct_aggr
        )

        self.tp1 = poem_models.ThresholdsProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='GROUP'
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.tp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'rules': [
                {
                    'host': 'hostFoo',
                    'metric': 'metricA',
                    'thresholds': 'freshness=1s;10;9:;0;25 entries=1;3;0:2;10'
                }
            ]
        })

        self.ver8 = poem_models.TenantHistory.objects.create(
            object_id=self.tp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.tp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=ct_tp
        )

        self.tp1.name = 'TEST_PROFILE2'
        self.tp1.groupname = 'NEW_GROUP'
        self.tp1.save()

        data = json.loads(
            serializers.serialize(
                'json', [self.tp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'rules': [
                {
                    'host': 'hostFoo',
                    'metric': 'newMetric',
                    'endpoint_group': 'test',
                    'thresholds': 'entries=1;3;0:2;10'
                }
            ]
        })

        self.ver9 = poem_models.TenantHistory.objects.create(
            object_id=self.tp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.tp1.__str__(),
            comment='[{"changed": {"fields": ["name", "groupname"]}}, '
                    '{"added": {"fields": ["rules"], '
                    '"object": ["newMetric"]}}, '
                    '{"deleted": {"fields": ["rules"], '
                    '"object": ["metricA"]}}]',
            user='testuser',
            content_type=ct_tp
        )

    def test_get_versions_of_metrics(self):
        request = self.factory.get(self.url + 'metric/argo.AMS-Check-new')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metric', 'argo.AMS-Check-new')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver2.id,
                    'object_repr': 'argo.AMS-Check-new',
                    'fields': {
                        'name': 'argo.AMS-Check-new',
                        'mtype': self.mtype1.name,
                        'group': 'TEST',
                        'probeversion': 'ams-probe (0.1.11)',
                        'parent': 'new-parent',
                        'probeexecutable': 'ams-probe-2',
                        'config': [
                            {'key': 'maxCheckAttempts', 'value': '4'},
                            {'key': 'timeout', 'value': '70'},
                            {'key': 'path',
                             'value':
                                 '/usr/libexec/argo-monitoring/probes/argo2'},
                            {'key': 'interval', 'value': '5'},
                            {'key': 'retryInterval', 'value': '4'}
                        ],
                        'attribute': [
                            {'key': 'argo.ams_TOKEN2', 'value': '--token'}
                        ],
                        'dependancy': [
                            {'key': 'new-key', 'value': 'new-value'}
                        ],
                        'flags': [],
                        'files': [],
                        'parameter': [],
                        'fileparameter': [
                            {'key': 'new-key', 'value': 'new-value'}
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver2.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Changed config fields "maxCheckAttempts", '
                               '"retryInterval" and "timeout". Changed group '
                               'and probekey.',
                    'version': datetime.datetime.strftime(
                        self.ver2.date_created, '%Y%m%d-%H%M%S'
                    )
                },
                {
                    'id': self.ver1.id,
                    'object_repr': 'argo.AMS-Check',
                    'fields': {
                        'name': 'argo.AMS-Check',
                        'mtype': self.mtype1.name,
                        'group': 'EGI',
                        'probeversion': 'ams-probe (0.1.7)',
                        'parent': '',
                        'probeexecutable': 'ams-probe',
                        'config': [
                            {'key': 'maxCheckAttempts', 'value': '3'},
                            {'key': 'timeout', 'value': '60'},
                            {'key': 'path',
                             'value':
                                 '/usr/libexec/argo-monitoring/probes/argo'},
                            {'key': 'interval', 'value': '5'},
                            {'key': 'retryInterval', 'value': '3'}
                        ],
                        'attribute': [
                            {'key': 'argo.ams_TOKEN', 'value': '--token'}
                        ],
                        'dependancy': [],
                        'flags': [
                            {'key': 'OBSESS', 'value': '1'}
                        ],
                        'files': [],
                        'parameter': [
                            {'key': '--project', 'value': 'EGI'}
                        ],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver1.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': datetime.datetime.strftime(
                        self.ver1.date_created, '%Y%m%d-%H%M%S'
                    )
                }
            ]
        )

    def test_get_passive_metric_version(self):
        request = self.factory.get(self.url + 'metric/org.apel.APEL-Pub')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metric', 'org.apel.APEL-Pub')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver3.id,
                    'object_repr': 'org.apel.APEL-Pub',
                    'fields': {
                        'name': 'org.apel.APEL-Pub',
                        'mtype': self.mtype2.name,
                        'group': 'EGI',
                        'probeversion': '',
                        'parent': '',
                        'probeexecutable': '',
                        'config': [],
                        'attribute': [],
                        'dependancy': [],
                        'flags': [
                            {'key': 'OBSESS', 'value': '1'},
                            {'key': 'PASSIVE', 'value': '1'}
                        ],
                        'files': [],
                        'parameter': [],
                        'fileparameter': []
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver3.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': datetime.datetime.strftime(
                        self.ver2.date_created, '%Y%m%d-%H%M%S'
                    )
                }
            ]
        )

    def test_get_nonexisting_metric_version(self):
        request = self.factory.get(self.url + 'metric/test.AMS-Check')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metric', 'test.AMS-Check')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Version not found.'})

    def test_get_nonexisting_metric(self):
        request = self.factory.get(self.url + 'metric/nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metric', 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Metric not found.'})

    def test_get_metric_version_without_specifying_name(self):
        request = self.factory.get(self.url + 'metric')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metric')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_metric_profile_versions(self):
        request = self.factory.get(self.url + 'metricprofile/TEST_PROFILE2')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metricprofile', 'TEST_PROFILE2')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver5.id,
                    'object_repr': 'TEST_PROFILE2',
                    'fields': {
                        'name': 'TEST_PROFILE2',
                        'groupname': 'NEW_GROUP',
                        'description': '',
                        'apiid': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'metricinstances': [
                            {'service': 'AMGA', 'metric': 'org.nagios.SAML-SP'},
                            {'service': 'APEL', 'metric': 'org.apel.APEL-Pub'}
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver5.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Deleted service-metric instance tuple '
                               '(APEL, org.apel.APEL-Sync). Changed groupname '
                               'and name.',
                    'version': datetime.datetime.strftime(
                        self.ver5.date_created, '%Y%m%d-%H%M%S'
                    )
                },
                {
                    'id': self.ver4.id,
                    'object_repr': 'TEST_PROFILE',
                    'fields': {
                        'name': 'TEST_PROFILE',
                        'groupname': 'EGI',
                        'description': '',
                        'apiid': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'metricinstances': [
                            {'service': 'AMGA', 'metric': 'org.nagios.SAML-SP'},
                            {'service': 'APEL', 'metric': 'org.apel.APEL-Pub'},
                            {'service': 'APEL', 'metric': 'org.apel.APEL-Sync'}
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver4.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': datetime.datetime.strftime(
                        self.ver4.date_created, '%Y%m%d-%H%M%S'
                    )
                }
            ]
        )

    def test_get_nonexisting_metricprofile(self):
        request = self.factory.get(self.url + 'metricprofile/nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metricprofile', 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Metric profile not found.'})

    def test_get_metric_version_without_specifying_name(self):
        request = self.factory.get(self.url + 'metricprofile')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'metricprofile')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_aggregation_profile_version(self):
        request = self.factory.get(
            self.url + 'aggregationprofile/TEST_PROFILE2'
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, 'aggregationprofile', 'TEST_PROFILE2')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver7.id,
                    'object_repr': 'TEST_PROFILE2',
                    'fields': {
                        'name': 'TEST_PROFILE2',
                        'description': '',
                        'groupname': 'TEST2',
                        'apiid': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'endpoint_group': 'servicegroups',
                        'metric_operation': 'OR',
                        'profile_operation': 'OR',
                        'metric_profile': 'TEST_PROFILE2',
                        'groups': [
                            {
                                'name': 'Group1a',
                                'operation': 'AND',
                                'services': [
                                    {
                                        'name': 'AMGA',
                                        'operation': 'OR'
                                    },
                                    {
                                        'name': 'APEL',
                                        'operation': 'OR'
                                    }
                                ]
                            },
                            {
                                'name': 'Group2',
                                'operation': 'OR',
                                'services': [
                                    {
                                        'name': 'argo.api',
                                        'operation': 'OR'
                                    }
                                ]
                            }
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver7.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Changed endpoint_group, groupname, '
                               'metric_operation, metric_profile, name and '
                               'profile_operation. Deleted groups field '
                               '"Group1". Added groups field "Group1a". '
                               'Changed groups field "Group2".',
                    'version': datetime.datetime.strftime(
                        self.ver7.date_created, '%Y%m%d-%H%M%S'
                    )
                },
                {
                    'id': self.ver6.id,
                    'object_repr': 'TEST_PROFILE',
                    'fields': {
                        'name': 'TEST_PROFILE',
                        'description': '',
                        'groupname': 'EGI',
                        'apiid': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
                        'endpoint_group': 'sites',
                        'metric_operation': 'AND',
                        'profile_operation': 'AND',
                        'metric_profile': 'TEST_PROFILE',
                        'groups': [
                            {
                                'name': 'Group1',
                                'operation': 'AND',
                                'services': [
                                    {
                                        'name': 'AMGA',
                                        'operation': 'OR'
                                    },
                                    {
                                        'name': 'APEL',
                                        'operation': 'OR'
                                    }
                                ]
                            },
                            {
                                'name': 'Group2',
                                'operation': 'AND',
                                'services': [
                                    {
                                        'name': 'VOMS',
                                        'operation': 'OR'
                                    },
                                    {
                                        'name': 'argo.api',
                                        'operation': 'OR'
                                    }
                                ]
                            }
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver6.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': datetime.datetime.strftime(
                        self.ver6.date_created, '%Y%m%d-%H%M%S'
                    )
                }
            ]
        )

    def test_get_nonexisting_aggregation_profile(self):
        request = self.factory.get(self.url + 'aggregationprofile/nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'aggregationprofile', 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'detail': 'Aggregation profile not found.'}
        )

    def test_get_aggregation_profile_version_without_specifying_name(self):
        request = self.factory.get(self.url + 'aggregationprofile')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'aggregationprofile')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_thresholds_profile_version(self):
        request = self.factory.get(
            self.url + 'thresholdsprofile/TEST_PROFILE2'
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, 'thresholdsprofile', 'TEST_PROFILE2')
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.ver9.id,
                    'object_repr': 'TEST_PROFILE2',
                    'fields': {
                        'name': 'TEST_PROFILE2',
                        'description': '',
                        'groupname': 'NEW_GROUP',
                        'apiid': self.tp1.apiid,
                        'rules': [
                            {
                                'host': 'hostFoo',
                                'metric': 'newMetric',
                                'endpoint_group': 'test',
                                'thresholds': 'entries=1;3;0:2;10'
                            }
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver9.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Changed name and groupname. '
                               'Added rule for metric "newMetric". '
                               'Deleted rule for metric "metricA".',
                    'version': datetime.datetime.strftime(
                        self.ver9.date_created, '%Y%m%d-%H%M%S'
                    )
                },
                {
                    'id': self.ver8.id,
                    'object_repr': 'TEST_PROFILE',
                    'fields': {
                        'name': 'TEST_PROFILE',
                        'description': '',
                        'groupname': 'GROUP',
                        'apiid': self.tp1.apiid,
                        'rules': [
                            {
                                'host': 'hostFoo',
                                'metric': 'metricA',
                                'thresholds': 'freshness=1s;10;9:;0;25 '
                                              'entries=1;3;0:2;10'
                            }
                        ]
                    },
                    'user': 'testuser',
                    'date_created': datetime.datetime.strftime(
                        self.ver8.date_created, '%Y-%m-%d %H:%M:%S'
                    ),
                    'comment': 'Initial version.',
                    'version': datetime.datetime.strftime(
                        self.ver8.date_created, '%Y%m%d-%H%M%S'
                    )
                }
            ]
        )


class ListYumReposAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListYumRepos.as_view()
        self.url = '/api/v2/internal/yumrepos/'
        self.user = CustUser.objects.create_user(username='testuser')

        self.tag1 = admin_models.OSTag.objects.create(name='CentOS 6')
        self.tag2 = admin_models.OSTag.objects.create(name='CentOS 7')

        self.repo1 = admin_models.YumRepo.objects.create(
            name='repo-1',
            tag=self.tag1,
            content='content1=content1\ncontent2=content2',
            description='Repo 1 description.'
        )

        self.repo2 = admin_models.YumRepo.objects.create(
            name='repo-2',
            tag=self.tag2,
            content='content1=content1\ncontent2=content2',
            description='Repo 2 description.'
        )

    def test_get_list_of_yum_repos(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'id': self.repo1.id,
                    'name': 'repo-1',
                    'tag': 'CentOS 6',
                    'content': 'content1=content1\ncontent2=content2',
                    'description': 'Repo 1 description.'
                },
                {
                    'id': self.repo2.id,
                    'name': 'repo-2',
                    'tag': 'CentOS 7',
                    'content': 'content1=content1\ncontent2=content2',
                    'description': 'Repo 2 description.'
                }
            ]
        )

    def test_get_yum_repo_by_name(self):
        request = self.factory.get(self.url + 'repo-1/centos6')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'repo-1', 'centos6')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                'id': self.repo1.id,
                'name': 'repo-1',
                'tag': 'CentOS 6',
                'content': 'content1=content1\ncontent2=content2',
                'description': 'Repo 1 description.'
            }
        )

    def test_get_yum_repo_in_case_of_nonexisting_name(self):
        request = self.factory.get(self.url + 'nonexisting/centos6')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting', 'centos6')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_yum_repo(self):
        data = {
            'name': 'repo-3',
            'tag': 'CentOS 6',
            'content': 'content1=content1\ncontent2=content2',
            'description': 'Repo 3 description'
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        repo = admin_models.YumRepo.objects.get(name='repo-3')
        self.assertEqual(repo.tag, self.tag1)
        self.assertEqual(
            repo.content,
            'content1=content1\ncontent2=content2'
        )
        self.assertEqual(repo.description, 'Repo 3 description')

    def test_post_yum_repo_with_name_and_tag_that_already_exist(self):
        data = {
            'name': 'repo-1',
            'tag': 'CentOS 6',
            'content': 'content1=content1\ncontent2=content2',
            'description': 'Another description.'
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'YUM repo with this name and tag already exists.'}
        )

    def test_put_yum_repo(self):
        data = {
            'id': self.repo1.id,
            'name': 'repo-new-1',
            'tag': 'CentOS 7',
            'content': 'content3=content3\ncontent4=content4',
            'description': 'Another description.'
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        repo = admin_models.YumRepo.objects.get(id=self.repo1.id)
        self.assertEqual(repo.name, 'repo-new-1')
        self.assertEqual(repo.tag, self.tag2)
        self.assertEqual(repo.name, 'repo-new-1')
        self.assertEqual(repo.content, 'content3=content3\ncontent4=content4')
        self.assertEqual(repo.description, 'Another description.')

    def test_put_yum_repo_with_existing_name_and_tag(self):
        data = {
            'id': self.repo1.id,
            'name': 'repo-2',
            'tag': 'CentOS 7',
            'content': 'content1=content1\ncontent2=content2',
            'description': 'Existing repo-2'
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'YUM repo with this name and tag already exists.'}
        )

    def test_put_yum_repo_with_existing_name_but_different_tag(self):
        data = {
            'id': self.repo1.id,
            'name': 'repo-2',
            'tag': 'CentOS 6',
            'content': 'content1=content1\ncontent2=content2',
            'description': 'Existing repo-2'
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        repo = admin_models.YumRepo.objects.get(id=self.repo1.id)
        self.assertEqual(repo.name, 'repo-2')
        self.assertEqual(repo.tag, self.tag1)
        self.assertEqual(repo.content, 'content1=content1\ncontent2=content2')
        self.assertEqual(repo.description, 'Existing repo-2')

    def test_delete_yum_repo(self):
        self.assertEqual(admin_models.YumRepo.objects.all().count(), 2)
        request = self.factory.delete(self.url + 'repo-1/centos6')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'repo-1', 'centos6')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(admin_models.YumRepo.objects.all().count(), 1)
        self.assertRaises(
            admin_models.YumRepo.DoesNotExist,
            admin_models.YumRepo.objects.get,
            name='repo-1'
        )

    def test_delete_yum_repo_without_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_yum_repo_nonexisting_name(self):
        request = self.factory.delete(self.url + 'nonexisting/centos7')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting', 'centos7')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'YUM repo not found.'})


class HistoryHelpersTests(TenantTestCase):
    def setUp(self):
        tag = admin_models.OSTag.objects.create(name='CentOS 6')
        self.repo = admin_models.YumRepo.objects.create(name='repo-1', tag=tag)

        self.package1 = admin_models.Package.objects.create(
            name='package-1',
            version='1.0.0'
        )
        self.package1.repos.add(self.repo)

        package2 = admin_models.Package.objects.create(
            name='package-1',
            version='1.0.1'
        )
        package2.repos.add(self.repo)

        package3 = admin_models.Package.objects.create(
            name='package-1',
            version='2.0.0'
        )

        self.probe1 = admin_models.Probe.objects.create(
            name='probe-1',
            package=self.package1,
            description='Some description.',
            comment='Some comment.',
            repository='https://repository.url',
            docurl='https://doc.url',
            user='testuser',
            datetime=datetime.datetime.now()
        )

        self.ct_metric = ContentType.objects.get_for_model(poem_models.Metric)
        self.ct_mp = ContentType.objects.get_for_model(
            poem_models.MetricProfiles
        )
        self.ct_aggr = ContentType.objects.get_for_model(
            poem_models.Aggregation
        )
        self.ct_tp = ContentType.objects.get_for_model(
            poem_models.ThresholdsProfiles
        )

        self.active = admin_models.MetricTemplateType.objects.create(
            name='Active'
        )
        self.metric_active = poem_models.MetricType.objects.create(
            name='Active'
        )

        probe_history1 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            version_comment='Initial version.',
            version_user='testuser'
        )

        self.probe1.package = package2
        self.probe1.comment = 'New version.'
        self.probe1.save()

        self.probe_history2 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            version_comment='[{"changed": {"fields": ["package", "comment"]}}]',
            version_user='testuser'
        )

        self.probe1.package = package3
        self.probe1.comment = 'Newest version.'
        self.probe1.save()

        self.probe_history3 = admin_models.ProbeHistory.objects.create(
            object_id=self.probe1,
            name=self.probe1.name,
            package=self.probe1.package,
            description=self.probe1.description,
            comment=self.probe1.comment,
            repository=self.probe1.repository,
            docurl=self.probe1.docurl,
            version_comment='[{"changed": {"fields": ["package", "comment"]}}]',
            version_user='testuser'
        )

        self.mt1 = admin_models.MetricTemplate.objects.create(
            name='metric-template-1',
            parent='["parent"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 3"]',
            attribute='["attribute-key attribute-value"]',
            dependency='["dependency-key1 dependency-value1", '
                       '"dependency-key2 dependency-value2"]',
            flags='["flags-key flags-value"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.active,
            probekey=probe_history1
        )

        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.mt1,
            name=self.mt1.name,
            mtype=self.mt1.mtype,
            probekey=self.mt1.probekey,
            parent=self.mt1.parent,
            probeexecutable=self.mt1.probeexecutable,
            config=self.mt1.config,
            attribute=self.mt1.attribute,
            dependency=self.mt1.dependency,
            flags=self.mt1.flags,
            files=self.mt1.files,
            parameter=self.mt1.parameter,
            fileparameter=self.mt1.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user='testuser'
        )

        self.mt1.probekey = self.probe_history2
        self.mt1.config = '["maxCheckAttempts 3", "timeout 70", ' \
                          '"path $USER", "interval 5", "retryInterval 3"]'
        self.mt1.save()

        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.mt1,
            name=self.mt1.name,
            mtype=self.mt1.mtype,
            probekey=self.mt1.probekey,
            parent=self.mt1.parent,
            probeexecutable=self.mt1.probeexecutable,
            config=self.mt1.config,
            attribute=self.mt1.attribute,
            dependency=self.mt1.dependency,
            flags=self.mt1.flags,
            files=self.mt1.files,
            parameter=self.mt1.parameter,
            fileparameter=self.mt1.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment='[{"changed": {"fields": ["config"], '
                            '"object": ["timeout"]}}, {"changed": {"fields": '
                            '["probekey"]}}]',
            version_user='testuser'
        )

        self.mt2 = admin_models.MetricTemplate.objects.create(
            name='metric-template-3',
            parent='["parent"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 3"]',
            attribute='["attribute-key attribute-value"]',
            dependency='["dependency-key1 dependency-value1", '
                       '"dependency-key2 dependency-value2"]',
            flags='["flags-key flags-value"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.active,
            probekey=probe_history1
        )

        admin_models.MetricTemplateHistory.objects.create(
            object_id=self.mt2,
            name=self.mt2.name,
            mtype=self.mt2.mtype,
            probekey=self.mt2.probekey,
            parent=self.mt2.parent,
            probeexecutable=self.mt2.probeexecutable,
            config=self.mt2.config,
            attribute=self.mt2.attribute,
            dependency=self.mt2.dependency,
            flags=self.mt2.flags,
            files=self.mt2.files,
            parameter=self.mt2.parameter,
            fileparameter=self.mt2.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user='testuser'
        )

        self.metric1 = poem_models.Metric.objects.create(
            name='metric-1',
            parent='["parent"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 3"]',
            attribute='["attribute-key attribute-value"]',
            dependancy='["dependency-key1 dependency-value1", '
                       '"dependency-key2 dependency-value2"]',
            flags='["flags-key flags-value"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.metric_active,
            probekey=probe_history1
        )

        poem_models.TenantHistory.objects.create(
            object_id=self.metric1.id,
            serialized_data=serializers.serialize(
                'json', [self.metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=self.metric1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct_metric
        )

        poem_models.GroupOfMetricProfiles.objects.create(name='TEST')
        poem_models.GroupOfMetricProfiles.objects.create(name='TEST2')

        self.mp1 = poem_models.MetricProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='TEST'
        )

        data = json.loads(serializers.serialize(
            'json', [self.mp1],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'metricinstances': [
                ('AMGA', 'org.nagios.SAML-SP'),
                ('APEL', 'org.apel.APEL-Pub'),
                ('APEL', 'org.apel.APEL-Sync')
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.mp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.mp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct_mp
        )

        poem_models.GroupOfAggregations.objects.create(name='TEST')
        poem_models.GroupOfAggregations.objects.create(name='TEST2')

        self.aggr1 = poem_models.Aggregation.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='TEST'
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.aggr1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'endpoint_group': 'sites',
            'metric_operation': 'AND',
            'profile_operation': 'AND',
            'metric_profile': 'TEST_PROFILE',
            'groups': [
                {
                    'name': 'Group1',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                },
                {
                    'name': 'Group2',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'VOMS',
                            'operation': 'OR'
                        },
                        {
                            'name':'argo.api',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.aggr1.id,
            serialized_data=json.dumps(data),
            object_repr=self.aggr1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct_aggr
        )

        self.tp1 = poem_models.ThresholdsProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='TEST'
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.tp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'rules': [
                {
                    'host': 'hostFoo',
                    'metric': 'metricA',
                    'thresholds': 'freshness=1s;10;9:;0;25 entries=1;3;0:2;10'
                }
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.tp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.tp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct_tp
        )

    def test_create_comment_for_metric_template(self):
        self.mt1.name = 'metric-template-2'
        self.mt1.probekey = self.probe_history3
        self.mt1.parent = ''
        self.mt1.probeexecutable = '["new-probeexecutable"]'
        self.mt1.dependency = '["dependency-key1 dependency-value1"]'
        self.mt1.flags = '["flags-key flags-value", "flags-key1 flags-value2"]'
        self.mt1.save()
        comment = create_comment(self.mt1)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"deleted": {"fields": ["dependency"], '
                '"object": ["dependency-key2"]}}',
                '{"added": {"fields": ["flags"], "object": ["flags-key1"]}}',
                '{"added": {"fields": ["probeexecutable"]}}',
                '{"changed": {"fields": ["name", "probekey"]}}',
                '{"deleted": {"fields": ["parent"]}}'
            }
        )

    def test_create_comment_for_metric_template_if_initial(self):
        mt = admin_models.MetricTemplate.objects.create(
            name='metric-template-2',
            probekey=self.probe_history2,
            probeexecutable='["new-probeexecutable"]',
            config='["maxCheckAttempts 4", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 4"]',
            attribute='["attribute-key attribute-value"]',
            dependency='["dependency-key1 dependency-value1"]',
            flags='["flags-key flags-value", "flags-key1 flags-value2"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.active
        )
        comment = create_comment(mt)
        self.assertEqual(comment, 'Initial version.')

    def test_update_comment_for_metric_template(self):
        self.mt1.name = 'metric-template-2'
        self.mt1.parent = ''
        self.mt1.probeexecutable = '["new-probeexecutable"]'
        self.mt1.dependency = '["dependency-key1 dependency-value1"]'
        self.mt1.flags = '["flags-key flags-value", "flags-key1 flags-value2"]'
        self.mt1.save()
        comment = update_comment(self.mt1)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["config"], "object": ["timeout"]}}',
                '{"deleted": {"fields": ["dependency"], '
                '"object": ["dependency-key2"]}}',
                '{"added": {"fields": ["flags"], "object": ["flags-key1"]}}',
                '{"added": {"fields": ["probeexecutable"]}}',
                '{"changed": {"fields": ["name", "probekey"]}}',
                '{"deleted": {"fields": ["parent"]}}'
            }
        )

    def test_do_not_update_comment_for_metric_template_if_initial(self):
        self.mt2.name = 'metric-template-4'
        self.mt2.parent = ''
        self.mt2.probeexecutable = '["new-probeexecutable"]'
        self.mt2.dependency = '["dependency-key1 dependency-value1"]'
        self.mt2.flags = '["flags-key flags-value", "flags-key1 flags-value2"]'
        self.mt2.save()
        comment = update_comment(self.mt2)
        self.assertEqual(comment, 'Initial version.')

    def test_create_comment_for_probe(self):
        package = admin_models.Package.objects.create(
            name='package',
            version='2.0.2'
        )
        package.repos.add(self.repo)
        self.probe1.name = 'probe-2'
        self.probe1.package = package
        self.probe1.description = 'Some new description.'
        self.probe1.comment = 'Newer version.'
        self.probe1.repository = 'https://repository2.url'
        self.probe1.docurl = 'https://doc2.url',
        self.probe1.save()
        comment = create_comment(self.probe1)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["comment", "description", "docurl", '
                '"name", "package", "repository"]}}'
            }
        )

    def test_update_comment_for_probe(self):
        package = admin_models.Package.objects.create(
            name='package',
            version='2.0.2'
        )
        package.repos.add(self.repo)
        self.probe1.name = 'probe-2'
        self.probe1.package = package
        self.probe1.save()
        comment = update_comment(self.probe1)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["comment", "name", "package"]}}'
            }
        )

    def test_do_not_update_comment_for_probe_if_initial(self):
        probe2 = admin_models.Probe.objects.create(
            name='probe-3',
            package=self.package1,
            description='Some description.',
            comment='Initial version.',
            repository='https://repository.url',
            docurl='https://doc.url',
            user='testuser',
            datetime=datetime.datetime.now()
        )
        admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            version_comment='Initial version.',
            version_user='testuser'
        )
        probe2.comment = 'Some comment.'
        probe2.save()
        comment = update_comment(probe2)
        self.assertEqual(comment, 'Initial version.')

    def test_create_comment_for_probe_if_initial(self):
        package = admin_models.Package.objects.create(
            name='package',
            version='1.0.2'
        )
        package.repos.add(self.repo)
        probe2 = admin_models.Probe.objects.create(
            name='probe-2',
            package=package,
            description='Some new description.',
            comment='Newer version.',
            repository='https://repository2.url',
            docurl='https://doc2.url',
            user='testuser',
            datetime=datetime.datetime.now()
        )
        comment = create_comment(probe2)
        self.assertEqual(comment, 'Initial version.')

    def test_create_comment_for_metric(self):
        metric = poem_models.Metric(
            name='metric-2',
            probekey=self.probe_history2,
            probeexecutable='["new-probeexecutable"]',
            config='["maxCheckAttempts 3", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 3"]',
            attribute='["attribute-key attribute-value"]',
            dependancy='["dependency-key1 dependency-value1"]',
            flags='["flags-key flags-value", "flags-key1 flags-value2"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.metric_active
        )
        serialized_data = serializers.serialize(
            'json', [metric],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        )
        comment = create_comment(self.metric1, self.ct_metric,
                                 serialized_data)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"deleted": {"fields": ["dependancy"], '
                '"object": ["dependency-key2"]}}',
                '{"added": {"fields": ["flags"], "object": ["flags-key1"]}}',
                '{"added": {"fields": ["probeexecutable"]}}',
                '{"changed": {"fields": ["name", "probekey"]}}',
                '{"deleted": {"fields": ["parent"]}}'
            }
        )

    def test_create_comment_for_metric_if_field_deleted_from_model(self):
        mt = poem_models.Metric(
            name='metric-2',
            probekey=self.probe_history2,
            probeexecutable='["new-probeexecutable"]',
            config='["maxCheckAttempts 4", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 3"]',
            attribute='["attribute-key attribute-value"]',
            dependancy='["dependency-key1 dependency-value1"]',
            flags='["flags-key flags-value", "flags-key1 flags-value2"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            mtype=self.metric_active
        )
        serialized_data = serializers.serialize(
            'json', [mt],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        )
        # let's say fileparameter field no longer exists in the model
        dict_serialized = json.loads(serialized_data)
        del dict_serialized[0]['fields']['fileparameter']
        new_serialized_data = json.dumps(dict_serialized)
        comment = create_comment(self.metric1, self.ct_metric,
                                 new_serialized_data)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["config"], '
                '"object": ["maxCheckAttempts"]}}',
                '{"deleted": {"fields": ["dependancy"], '
                '"object": ["dependency-key2"]}}',
                '{"added": {"fields": ["flags"], "object": ["flags-key1"]}}',
                '{"added": {"fields": ["probeexecutable"]}}',
                '{"changed": {"fields": ["name", "probekey"]}}',
                '{"deleted": {"fields": ["parent"]}}'
            }
        )

    def test_create_comment_for_metric_if_field_added_to_model(self):
        mt = poem_models.Metric(
            name='metric-2',
            probekey=self.probe_history2,
            probeexecutable='["new-probeexecutable"]',
            config='["maxCheckAttempts 4", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 4"]',
            attribute='["attribute-key attribute-value"]',
            dependancy='["dependency-key1 dependency-value1"]',
            flags='["flags-key flags-value", "flags-key1 flags-value2"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.metric_active
        )
        serialized_data = serializers.serialize(
            'json', [mt],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        )
        # let's say mock_field was added to model
        dict_serialized = json.loads(serialized_data)
        dict_serialized[0]['fields']['mock_field'] = 'mock_value'
        new_serialized_data = json.dumps(dict_serialized)
        comment = create_comment(self.metric1, self.ct_metric,
                                 new_serialized_data)
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["config"], '
                '"object": ["maxCheckAttempts", "retryInterval"]}}',
                '{"deleted": {"fields": ["dependancy"], '
                '"object": ["dependency-key2"]}}',
                '{"added": {"fields": ["flags"], "object": ["flags-key1"]}}',
                '{"added": {"fields": ["mock_field", "probeexecutable"]}}',
                '{"changed": {"fields": ["name", "probekey"]}}',
                '{"deleted": {"fields": ["parent"]}}'
            }
        )

    def test_create_comment_for_metric_if_initial(self):
        mt = poem_models.Metric.objects.create(
            name='metric-template-2',
            probekey=self.probe_history2,
            probeexecutable='["new-probeexecutable"]',
            config='["maxCheckAttempts 4", "timeout 60",'
                   ' "path $USER", "interval 5", "retryInterval 4"]',
            attribute='["attribute-key attribute-value"]',
            dependancy='["dependency-key1 dependency-value1"]',
            flags='["flags-key flags-value", "flags-key1 flags-value2"]',
            files='["files-key files-value"]',
            parameter='["parameter-key parameter-value"]',
            fileparameter='["fileparameter-key fileparameter-value"]',
            mtype=self.metric_active
        )
        serialized_data = serializers.serialize(
            'json', [mt],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        )
        comment = create_comment(mt, self.ct_metric, serialized_data)
        self.assertEqual(comment, 'Initial version.')

    def test_create_comment_for_metric_if_group_was_none(self):
        group = poem_models.GroupOfMetrics.objects.create(name='EGI')
        m = self.metric1
        m.group = group
        m.save()
        serialized_data = serializers.serialize(
            'json', [m],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        )
        comment = create_comment(m, self.ct_metric, serialized_data)
        self.assertEqual(comment, '[{"added": {"fields": ["group"]}}]')

    def test_create_comment_for_metricprofile(self):
        self.mp1.name = 'TEST_PROFILE2',
        self.mp1.groupname = 'TEST2'
        self.mp1.save()
        data = json.loads(serializers.serialize(
            'json', [self.mp1],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'metricinstances': [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['ARC-CE', 'org.nordugrid.ARC-CE-IGTF']
            ]
        })
        comment = create_comment(self.mp1, self.ct_mp, json.dumps(data))
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["groupname", "name"]}}',
                '{"added": {"fields": ["metricinstances"], '
                '"object": ["ARC-CE", "org.nordugrid.ARC-CE-IGTF"]}}',
                '{"deleted": {"fields": ["metricinstances"], '
                '"object": ["APEL", "org.apel.APEL-Sync"]}}'
            }
        )

    def test_create_comment_for_metricprofile_if_initial(self):
        mp = poem_models.MetricProfiles.objects.create(
            name='TEST_PROFILE2',
            groupname='TEST',
            apiid='10000000-oooo-kkkk-aaaa-aaeekkccnnee'
        )
        data = json.loads(serializers.serialize(
            'json', [mp],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'metricinstances': [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['ARC-CE', 'org.nordugrid.ARC-CE-IGTF']
            ]
        })
        comment = create_comment(mp, self.ct_mp, json.dumps(data))
        self.assertEqual(comment, 'Initial version.')

    def test_create_comment_for_aggregation_profile(self):
        self.aggr1.name = 'TEST_PROFILE2'
        self.aggr1.groupname = 'TEST2'
        data = json.loads(serializers.serialize(
            'json', [self.aggr1],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'endpoint_group': 'servicegroups',
            'metric_operation': 'OR',
            'profile_operation': 'OR',
            'metric_profile': 'TEST_PROFILE2',
            'groups': [
                {
                    'name': 'Group1a',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                },
                {
                    'name': 'Group2',
                    'operation': 'OR',
                    'services': [
                        {
                            'name': 'argo.api',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })
        comment = create_comment(self.aggr1, self.ct_aggr, json.dumps(data))
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["endpoint_group", "groupname", '
                '"metric_operation", "metric_profile", "name", '
                '"profile_operation"]}}',
                '{"deleted": {"fields": ["groups"], "object": ["Group1"]}}',
                '{"added": {"fields": ["groups"], "object": ["Group1a"]}}',
                '{"changed": {"fields": ["groups"], "object": ["Group2"]}}'
            }
        )
        self.aggr1.save()

    def test_create_comment_for_aggregationprofile_if_initial(self):
        aggr = poem_models.Aggregation.objects.create(
            name='TEST_PROFILE2',
            groupname='TEST',
            apiid='10000000-oooo-kkkk-aaaa-aaeekkccnnee'
        )
        data = json.loads(serializers.serialize(
            'json', [aggr],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'endpoint_group': 'servicegroups',
            'metric_operation': 'OR',
            'profile_operation': 'OR',
            'metric_profile': 'TEST_PROFILE2',
            'groups': [
                {
                    'name': 'Group1a',
                    'operation': 'AND',
                    'services': [
                        {
                            'name': 'AMGA',
                            'operation': 'OR'
                        },
                        {
                            'name': 'APEL',
                            'operation': 'OR'
                        }
                    ]
                }
            ]
        })
        comment = create_comment(aggr, self.ct_aggr, json.dumps(data))
        self.assertEqual(comment, 'Initial version.')

    def test_create_comment_for_thresholds_profile(self):
        self.tp1.name = 'TEST_PROFILE2'
        self.tp1.groupname = 'TEST2'
        self.tp1.save()
        data = json.loads(serializers.serialize(
            'json', [self.tp1],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'rules': [
                {
                    'host': 'hostFoo',
                    'metric': 'metricA',
                    'thresholds': 'freshness=1s;10;9:;0;25'
                },
                {
                    'host': 'hostBar',
                    'endpoint_group': 'TEST-SITE-51',
                    'metric': 'httpd.ResponseTime',
                    'thresholds': 'response=20ms;0:500;499:1000'
                },
                {
                    'metric': 'httpd.ResponseTime',
                    'thresholds': 'response=20ms;0:300;299:1000'
                }
            ]
        })
        comment = create_comment(self.tp1, self.ct_tp, json.dumps(data))
        comment_set = set()
        for item in json.loads(comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["groupname", "name"]}}',
                '{"changed": {"fields": ["rules"], "object": ["metricA"]}}',
                '{"added": {"fields": ["rules"], '
                '"object": ["httpd.ResponseTime"]}}',
            }
        )

    def test_create_comment_for_thresholds_profile_if_initial(self):
        tp = poem_models.ThresholdsProfiles.objects.create(
            name='TEST_PROFILE2',
            groupname='TEST',
            apiid='10000000-oooo-kkkk-aaaa-aaeekkccnnee'
        )
        data = json.loads(serializers.serialize(
            'json', [tp],
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        ))
        data[0]['fields'].update({
            'rules': [
                {
                    'host': 'hostBar',
                    'endpoint_group': 'TEST-SITE-51',
                    'metric': 'httpd.ResponseTime',
                    'thresholds': 'response=20ms;0:500;499:1000'
                },
                {
                    'metric': 'httpd.ResponseTime',
                    'thresholds': 'response=20ms;0:300;299:1000'
                }
            ]
        })
        comment = create_comment(tp, self.ct_tp, json.dumps(data))
        self.assertEqual(comment, 'Initial version.')


class ListThresholdsProfilesInGroupAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListThresholdsProfilesInGroup.as_view()
        self.url = '/api/v2/internal/thresholdsprofilesgroup/'
        self.user = CustUser.objects.create_user(username='testuser')

        self.tp1 = poem_models.ThresholdsProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.tp2 = poem_models.ThresholdsProfiles.objects.create(
            name='ANOTHER_PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )

        self.tp3 = poem_models.ThresholdsProfiles.objects.create(
            name='DELETE_PROFILE',
            apiid='12341234-hhhh-kkkk-aaaa-aaeekkccnnee',
            groupname='delete'
        )

        self.group = poem_models.GroupOfThresholdsProfiles.objects.create(
            name='EGI'
        )
        group2 = poem_models.GroupOfThresholdsProfiles.objects.create(
            name='delete'
        )
        self.group.thresholdsprofiles.add(self.tp1)
        group2.thresholdsprofiles.add(self.tp3)

    def test_get_thresholds_profiles_in_group(self):
        request = self.factory.get(self.url + 'EGI')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'EGI')
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.tp1.id, 'name': 'TEST_PROFILE'}
                ]
            }
        )

    def test_get_thresholds_profiles_in_group_in_case_no_authorization(self):
        request = self.factory.get(self.url + 'EGI')
        response = self.view(request, 'EGI')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_thresholds_profiles_without_group(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            {
                'result': [
                    {'id': self.tp2.id, 'name': 'ANOTHER_PROFILE'}
                ]
            }
        )

    def test_add_thresholds_profile_in_group(self):
        self.assertEqual(self.group.thresholdsprofiles.count(), 1)
        data = {
            'name': 'EGI',
            'items': ['TEST_PROFILE', 'ANOTHER_PROFILE']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tp1 = poem_models.ThresholdsProfiles.objects.get(name='TEST_PROFILE')
        tp2 = poem_models.ThresholdsProfiles.objects.get(name='ANOTHER_PROFILE')
        self.assertEqual(tp1.groupname, 'EGI')
        self.assertEqual(tp2.groupname, 'EGI')
        self.assertEqual(self.group.thresholdsprofiles.count(), 2)

    def test_remove_thresholds_profile_from_group(self):
        self.group.thresholdsprofiles.add(self.tp2)
        self.assertEqual(self.group.thresholdsprofiles.all().count(), 2)
        data = {
            'name': 'EGI',
            'items': ['ANOTHER_PROFILE']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tp1 = poem_models.ThresholdsProfiles.objects.get(name='TEST_PROFILE')
        tp2 = poem_models.ThresholdsProfiles.objects.get(name='ANOTHER_PROFILE')
        self.assertEqual(tp1.groupname, '')
        self.assertEqual(tp2.groupname, 'EGI')
        self.assertEqual(self.group.thresholdsprofiles.count(), 1)

    def test_post_thresholds_profile_group_without_tp(self):
        self.assertEqual(
            poem_models.GroupOfThresholdsProfiles.objects.all().count(), 2
        )
        data = {
            'name': 'new_group',
            'items': []
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.GroupOfThresholdsProfiles.objects.all().count(), 3
        )
        group = poem_models.GroupOfThresholdsProfiles.objects.get(
            name='new_group'
        )
        self.assertEqual(group.name, 'new_group')
        self.assertEqual(group.thresholdsprofiles.count(), 0)

    def test_post_thresholds_profile_group_with_tp(self):
        self.assertEqual(
            poem_models.GroupOfThresholdsProfiles.objects.all().count(), 2
        )
        data = {
            'name': 'new_group',
            'items': ['ANOTHER_PROFILE']
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.GroupOfThresholdsProfiles.objects.all().count(), 3
        )
        group = poem_models.GroupOfThresholdsProfiles.objects.get(
            name='new_group'
        )
        self.assertEqual(group.name, 'new_group')
        self.assertEqual(group.thresholdsprofiles.count(), 1)
        tp1 = poem_models.ThresholdsProfiles.objects.get(name='TEST_PROFILE')
        tp2 = poem_models.ThresholdsProfiles.objects.get(name='ANOTHER_PROFILE')
        self.assertEqual(tp1.groupname, 'EGI')
        self.assertEqual(tp2.groupname, 'new_group')

    def test_post_thresholds_profile_group_with_name_that_already_exists(self):
        data = {
            'name': 'EGI',
            'items': ['TEST_PROFILE']
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                'detail':
                    'Thresholds profiles group with this name already exists.'
            }
        )

    def test_delete_thresholds_profile_group(self):
        self.assertEqual(
            poem_models.GroupOfThresholdsProfiles.objects.all().count(), 2
        )
        request = self.factory.delete(self.url + 'delete')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'delete')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            poem_models.GroupOfThresholdsProfiles.objects.all().count(), 1
        )
        self.assertRaises(
            poem_models.GroupOfThresholdsProfiles.DoesNotExist,
            poem_models.GroupOfThresholdsProfiles.objects.get,
            name='delete'
        )
        tp = poem_models.ThresholdsProfiles.objects.get(name='DELETE_PROFILE')
        self.assertEqual(tp.groupname, '')

    def test_delete_nonexisting_thresholds_profile_group(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_thresholds_profile_group_without_specifying_name(self):
        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListThresholdsProfilesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListThresholdsProfiles.as_view()
        self.url = '/api/v2/internal/thresholdsprofiles/'
        self.user = CustUser.objects.create_user(username='testuser')

        self.tp1 = poem_models.ThresholdsProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='GROUP'
        )

        self.tp2 = poem_models.ThresholdsProfiles.objects.create(
            name='ANOTHER_PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee'
        )

        poem_models.GroupOfThresholdsProfiles.objects.create(name='GROUP')
        poem_models.GroupOfThresholdsProfiles.objects.create(name='NEWGROUP')

        self.ct = ContentType.objects.get_for_model(
            poem_models.ThresholdsProfiles
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.tp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'rules': [
                {
                    'host': 'hostFoo',
                    'metric': 'metricA',
                    'thresholds': 'freshness=1s;10;9:;0;25 entries=1;3;0:2;10'
                }
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.tp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.tp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.tp2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'rules': [
                {
                    'metric': 'metricB',
                    'thresholds': 'freshness=1s;10;9:;0;25'
                }
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.tp2.id,
            serialized_data=json.dumps(data),
            object_repr=self.tp2.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=self.ct
        )

    @patch('Poem.api.internal_views.thresholdsprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_all_thresholds_profiles(self, func):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                OrderedDict([
                    ('name', 'ANOTHER_PROFILE'),
                    ('description', ''),
                    ('apiid', '12341234-oooo-kkkk-aaaa-aaeekkccnnee'),
                    ('groupname', '')
                ]),
                OrderedDict([
                    ('name', 'TEST_PROFILE'),
                    ('description', ''),
                    ('apiid', '00000000-oooo-kkkk-aaaa-aaeekkccnnee'),
                    ('groupname', 'GROUP')
                ])
            ]
        )

    @patch('Poem.api.internal_views.thresholdsprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_thresholds_profiles_if_no_authentication(self, func):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('Poem.api.internal_views.thresholdsprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_thresholds_profile_by_name(self, func):
        request = self.factory.get(self.url + 'TEST_PROFILE')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'TEST_PROFILE')
        self.assertEqual(
            response.data,
            OrderedDict([
                ('name', 'TEST_PROFILE'),
                ('description', ''),
                ('apiid', '00000000-oooo-kkkk-aaaa-aaeekkccnnee'),
                ('groupname', 'GROUP')
            ])
        )

    @patch('Poem.api.internal_views.thresholdsprofiles.sync_webapi',
           side_effect=mocked_func)
    def test_get_thresholds_profile_by_nonexisting_name(self, func):
        request = self.factory.get(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {'detail': 'Thresholds profile not found.'}
        )

    def put_thresholds_profile(self):
        data = {
            'name': 'NEW_TEST_PROFILE',
            'apiid': '00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            'group': 'NEWGROUP',
            'rules': json.dumps([
                {
                    'host': 'newHost',
                    'metric': 'newMetric',
                    'thresholds': 'entries=1;3;0:2;10'
                }
            ])
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tp = poem_models.ThresholdsProfiles.objects.get(id=self.tp1.id)
        self.assertEqual(tp.name, 'NEW_TEST_PROFILE')
        self.assertEqual(tp.groupname, 'NEWGROUP')
        group1 = poem_models.GroupOfThresholdsProfiles.objects.get(
            name='NEWGROUP'
        )
        group2 = poem_models.GroupOfThresholdsProfiles.objects.get(
            name='GROUP'
        )
        self.assertTrue(
            group1.thresholdsprofiles.filter(
                apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee'
            ).exists()
        )
        self.assertFalse(
            group2.thresholdsprofiles.filter(
                apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee'
            ).exists()
        )
        history = poem_models.TenantHistory.objects.filter(
            object_id=tp.id, content_type=self.ct
        ).order_by('-date_created')
        self.assertEqual(history.count(), 2)
        comment_set = set()
        for item in json.loads(history[0].comment):
            comment_set.add(json.dumps(item))
        self.assertEqual(
            comment_set,
            {
                '{"changed": {"fields": ["groupname", "name"]}}',
                '{"deleted": {"fields": ["rules"], "object": ["metricA"]}}',
                '{"added": {"fields": ["rules"], "object": ["newMetric"]}}'
            }
        )
        serialized_data = json.loads(history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], tp.name)
        self.assertEqual(serialized_data['groupname'], tp.groupname)
        self.assertEqual(serialized_data['apiid'], tp.apiid)
        self.assertEqual(
            serialized_data['rules'],
            [
                {
                    'host': 'newHost',
                    'metric': 'newMetric',
                    'thresholds': 'entries=1;3;0:2;10'
                }
            ]
        )

    def post_thresholds_profile(self):
        self.assertEqual(
            poem_models.ThresholdsProfiles.objects.all().count(), 2
        )
        data = {
            'name': 'NEW_PROFILE',
            'apiid': '12341234-aaaa-kkkk-aaaa-aaeekkccnnee',
            'groupname': 'GROUP',
            'rules': json.dumps([
                {
                    'host': 'newHost',
                    'metric': 'newMetric',
                    'thresholds': 'entries=1;3;0:2;10'
                }
            ])
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            poem_models.ThresholdsProfiles.objects.all().count(), 3
        )
        profile = poem_models.ThresholdsProfiles.objects.get(
            apiid='12341234-aaaa-kkkk-aaaa-aaeekkccnnee'
        )
        self.assertEqual(profile.name, 'NEW_PROFILE')
        self.assertEqual(profile.groupname, 'GROUP')
        group = poem_models.GroupOfThresholdsProfiles.objects.get(name='GROUP')
        self.assertTrue(
            group.thresholdsprofiles.filter(
                apiid='12341234-aaaa-kkkk-aaaa-aaeekkccnnee'
            ).exists()
        )
        history = poem_models.TenantHistory.objects.filter(
            object_id=profile.id, content_type=self.ct
        ).order_by('-date_created')
        self.assertEqual(history.count(), 1)
        self.assertEqual(history[0].comment, 'Initial version.')
        serialized_data = json.loads(history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], profile.name)
        self.assertEqual(serialized_data['apiid'], profile.apiid)
        self.assertEqual(serialized_data['groupname'], profile.groupname)
        self.assertEqual(
            serialized_data['rules'],
            [
                {
                    'host': 'newHost',
                    'metric': 'newMetric',
                    'thresholds': 'entries=1;3;0:2;10'
                }
            ]
        )

    def delete_thresholds_profile(self):
        self.assertEqual(
            poem_models.ThresholdsProfiles.objects.all().count(), 2
        )
        self.assertEqual(
            poem_models.TenantHistory.objects.filter(
                object_id=self.tp1.id, content_type=self.ct
            ).count(), 1
        )
        request = self.factory.delete(
            self.url + '00000000-oooo-kkkk-aaaa-aaeekkccnnee'
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, '00000000-oooo-kkkk-aaaa-aaeekkccnnee')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertRaises(
            poem_models.ThresholdsProfiles.DoesNotExist,
            poem_models.ThresholdsProfiles.objects.get,
            id=self.tp1.id
        )
        self.assertEqual(
            poem_models.TenantHistory.objects.filter(
                object_id=self.tp1.id, content_type=self.ct
            ).count(), 0
        )

    def delete_nonexisting_thresholds_profile(self):
        request = self.factory.delete(self.url + 'nonexisting')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status.code, status.HTTP_404_NOT_FOUND)


class ListPackagesAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListPackages.as_view()
        self.url = '/api/v2/internal/packages/'
        self.user = CustUser.objects.create_user(username='testuser')

        with schema_context(get_public_schema_name()):
            Tenant.objects.create(name='public', domain_url='public',
                                  schema_name=get_public_schema_name())

        self.tag1 = admin_models.OSTag.objects.create(name='CentOS 6')
        self.tag2 = admin_models.OSTag.objects.create(name='CentOS 7')
        self.repo1 = admin_models.YumRepo.objects.create(
            name='repo-1', tag=self.tag1
        )
        self.repo2 = admin_models.YumRepo.objects.create(
            name='repo-2', tag=self.tag2
        )

        self.package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        self.package1.repos.add(self.repo1, self.repo2)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-globus',
            version='0.1.5'
        )
        package2.repos.add(self.repo2)

        package3 = admin_models.Package.objects.create(
            name='nagios-plugins-fedcloud',
            version='0.5.0'
        )
        package3.repos.add(self.repo2)

        self.package4 = admin_models.Package.objects.create(
            name='nagios-plugins-http',
            use_present_version=True
        )
        self.package4.repos.add(self.repo1, self.repo2)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=self.package1,
            description='Probe is inspecting AMS service by trying to publish '
                        'and consume randomly generated messages.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md',
            user='testuser',
            datetime=datetime.datetime.now()
        )

        pv1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            version_comment='Initial version.',
            version_user=self.user.username
        )

        mtype = admin_models.MetricTemplateType.objects.create(name='Active')
        metrictype = poem_models.MetricType.objects.create(name='Active')

        group = poem_models.GroupOfMetrics.objects.create(name='TEST')

        ct = ContentType.objects.get_for_model(poem_models.Metric)

        mt = admin_models.MetricTemplate.objects.create(
            name='argo.AMS-Check',
            mtype=mtype,
            probekey=pv1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        admin_models.MetricTemplateHistory.objects.create(
            object_id=mt,
            name=mt.name,
            mtype=mt.mtype,
            probekey=mt.probekey,
            parent=mt.parent,
            probeexecutable=mt.probeexecutable,
            config=mt.config,
            attribute=mt.attribute,
            dependency=mt.dependency,
            flags=mt.flags,
            files=mt.files,
            parameter=mt.parameter,
            fileparameter=mt.fileparameter,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        metric1 = poem_models.Metric.objects.create(
            name='argo.AMS-Check',
            group=group,
            mtype=metrictype,
            probekey=pv1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        poem_models.TenantHistory.objects.create(
            object_id=metric1.id,
            serialized_data=serializers.serialize(
                'json', [metric1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            ),
            object_repr=metric1.__str__(),
            content_type=ct,
            date_created=datetime.datetime.now(),
            comment='Initial version.',
            user=self.user.username
        )

    def test_get_list_of_packages(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'name': 'nagios-plugins-argo',
                    'version': '0.1.11',
                    'use_present_version': False,
                    'repos': ['repo-1 (CentOS 6)', 'repo-2 (CentOS 7)']
                },
                {
                    'name': 'nagios-plugins-fedcloud',
                    'version': '0.5.0',
                    'use_present_version': False,
                    'repos': ['repo-2 (CentOS 7)']
                },
                {
                    'name': 'nagios-plugins-globus',
                    'version': '0.1.5',
                    'use_present_version': False,
                    'repos': ['repo-2 (CentOS 7)']
                },
                {
                    'name': 'nagios-plugins-http',
                    'version': 'present',
                    'use_present_version': True,
                    'repos': ['repo-1 (CentOS 6)', 'repo-2 (CentOS 7)']
                }
            ]
        )

    def test_access_denied_if_no_authn(self):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_package_by_name_and_version(self):
        request = self.factory.get(self.url + 'nagios-plugins-argo-0.1.11')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nagios-plugins-argo-0.1.11')
        self.assertEqual(
            response.data,
            {
                'id': self.package1.id,
                'name': 'nagios-plugins-argo',
                'version': '0.1.11',
                'use_present_version': False,
                'repos': ['repo-1 (CentOS 6)', 'repo-2 (CentOS 7)']
            }
        )

    def test_get_package_by_name_if_present_version(self):
        request = self.factory.get(self.url + 'nagios-plugins-http-present')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nagios-plugins-http-present')
        self.assertEqual(
            response.data,
            {
                'id': self.package4.id,
                'name': 'nagios-plugins-http',
                'version': 'present',
                'use_present_version': True,
                'repos': ['repo-1 (CentOS 6)', 'repo-2 (CentOS 7)']
            }
        )

    def test_get_package_by_nonexisting_name_and_version(self):
        request = self.factory.get(self.url + 'nonexisting-0.1.1')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting-0.1.1')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'detail': 'Package not found.'})

    def test_post_package(self):
        data = {
            'name': 'nagios-plugins-activemq',
            'version': '1.0.0',
            'use_present_version': False,
            'repos': ['repo-1 (CentOS 6)', 'repo-2 (CentOS 7)']
        }
        self.assertEqual(admin_models.Package.objects.all().count(), 4)
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(admin_models.Package.objects.all().count(), 5)
        package = admin_models.Package.objects.get(
            name='nagios-plugins-activemq', version='1.0.0'
        )
        self.assertEqual(package.repos.all().count(), 2)
        self.assertTrue(self.repo1 in package.repos.all())
        self.assertTrue(self.repo2 in package.repos.all())

    def test_post_package_with_present_version(self):
        data = {
            'name': 'nagios-plugins-tcp',
            'version': '2.2.2',
            'use_present_version': True,
            'repos': ['repo-1 (CentOS 6)', 'repo-2 (CentOS 7)']
        }
        self.assertEqual(admin_models.Package.objects.all().count(), 4)
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(admin_models.Package.objects.all().count(), 5)
        self.assertRaises(
            admin_models.Package.DoesNotExist,
            admin_models.Package.objects.get,
            name='nagios-plugins-tcp', version='2.2.2'
        )
        package = admin_models.Package.objects.get(
            name='nagios-plugins-tcp', version='present'
        )
        self.assertEqual(package.repos.all().count(), 2)
        self.assertTrue(self.repo1 in package.repos.all())
        self.assertTrue(self.repo2 in package.repos.all())

    def test_post_package_with_name_and_version_which_already_exist(self):
        data = {
            'name': 'nagios-plugins-argo',
            'version': '0.1.11',
            'use_present_version': False,
            'repos': ['repo-1 (CentOS 6)']
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Package with this name and version already exists.'}
        )

    def test_post_package_with_name_that_exists_and_new_version(self):
        data = {
            'name': 'nagios-plugins-argo',
            'version': '0.1.7',
            'use_present_version': False,
            'repos': ['repo-2 (CentOS 7)']
        }
        self.assertEqual(admin_models.Package.objects.all().count(), 4)
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(admin_models.Package.objects.all().count(), 5)
        package = admin_models.Package.objects.get(
            name='nagios-plugins-argo', version='0.1.7'
        )
        self.assertEqual(package.repos.all().count(), 1)
        self.assertTrue(self.repo2 in package.repos.all())

    def test_post_package_with_with_repo_without_tag(self):
        data = {
            'name': 'nagios-plugins-activemq',
            'version': '1.0.0',
            'use_present_version': False,
            'repos': ['repo-1']
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data, {'detail': 'You should specify YUM repo tag!'}
        )

    def test_post_package_with_with_nonexisting_repo(self):
        data = {
            'name': 'nagios-plugins-activemq',
            'version': '1.0.0',
            'use_present_version': False,
            'repos': ['nonexisting (CentOS 7)']
        }
        request = self.factory.post(self.url, data, format='json')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'detail': 'YUM repo not found.'}
        )

    def test_put_package(self):
        data = {
            'id': self.package1.id,
            'name': 'nagios-plugins-argo2',
            'version': '0.1.7',
            'use_present_version': False,
            'repos': ['repo-2 (CentOS 7)']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        package = admin_models.Package.objects.get(id=self.package1.id)
        self.assertEqual(package.name, 'nagios-plugins-argo2')
        self.assertEqual(package.version, '0.1.7')
        self.assertEqual(package.repos.all().count(), 1)
        self.assertTrue(self.repo2 in package.repos.all())
        probe = admin_models.Probe.objects.get(name='ams-probe')
        self.assertEqual(probe.package, package)
        probe_history = admin_models.ProbeHistory.objects.filter(
            object_id=probe
        ).order_by('-date_created')
        self.assertEqual(probe_history.count(), 1)
        self.assertEqual(probe_history[0].package, probe.package)
        mt = admin_models.MetricTemplate.objects.get(name='argo.AMS-Check')
        self.assertEqual(mt.probekey, probe_history[0])
        mt_history = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(mt_history[0].probekey, probe_history[0])
        metric = poem_models.Metric.objects.get(name='argo.AMS-Check')
        self.assertEqual(metric.probekey, probe_history[0])
        metric_history = poem_models.TenantHistory.objects.filter(
            object_repr=metric.__str__()
        ).order_by('-date_created')
        self.assertEqual(metric_history.count(), 1)
        serialized_data = \
            json.loads(metric_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['probekey'], ['ams-probe', '0.1.7'])

    def test_put_package_with_present_version(self):
        data = {
            'id': self.package1.id,
            'name': 'nagios-plugins-argo2',
            'version': '0.1.7',
            'use_present_version': True,
            'repos': ['repo-2 (CentOS 7)']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        package = admin_models.Package.objects.get(id=self.package1.id)
        self.assertEqual(package.name, 'nagios-plugins-argo2')
        self.assertEqual(package.version, 'present')
        self.assertEqual(package.repos.all().count(), 1)
        self.assertTrue(self.repo2 in package.repos.all())
        probe = admin_models.Probe.objects.get(name='ams-probe')
        self.assertEqual(probe.package, package)
        probe_history = admin_models.ProbeHistory.objects.filter(
            object_id=probe
        ).order_by('-date_created')
        self.assertEqual(probe_history.count(), 1)
        self.assertEqual(probe_history[0].package, probe.package)
        mt = admin_models.MetricTemplate.objects.get(name='argo.AMS-Check')
        self.assertEqual(mt.probekey, probe_history[0])
        mt_history = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(mt_history[0].probekey, probe_history[0])
        metric = poem_models.Metric.objects.get(name='argo.AMS-Check')
        self.assertEqual(metric.probekey, probe_history[0])
        metric_history = poem_models.TenantHistory.objects.filter(
            object_repr=metric.__str__()
        ).order_by('-date_created')
        self.assertEqual(metric_history.count(), 1)
        serialized_data = \
            json.loads(metric_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['probekey'], ['ams-probe', 'present'])

    def test_put_package_with_new_repo(self):
        repo = admin_models.YumRepo.objects.create(name='repo-3', tag=self.tag1)
        data = {
            'id': self.package1.id,
            'name': 'nagios-plugins-argo2',
            'version': '0.1.7',
            'use_present_version': False,
            'repos': ['repo-2 (CentOS 7)', 'repo-3 (CentOS 6)']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        package = admin_models.Package.objects.get(id=self.package1.id)
        self.assertEqual(package.name, 'nagios-plugins-argo2')
        self.assertEqual(package.version, '0.1.7')
        self.assertEqual(package.repos.all().count(), 2)
        self.assertTrue(self.repo2 in package.repos.all())
        self.assertTrue(repo in package.repos.all())
        probe = admin_models.Probe.objects.get(name='ams-probe')
        self.assertEqual(probe.package, package)
        probe_history = admin_models.ProbeHistory.objects.filter(
            object_id=probe
        ).order_by('-date_created')
        self.assertEqual(probe_history.count(), 1)
        self.assertEqual(probe_history[0].package, probe.package)
        mt = admin_models.MetricTemplate.objects.get(name='argo.AMS-Check')
        self.assertEqual(mt.probekey, probe_history[0])
        mt_history = admin_models.MetricTemplateHistory.objects.filter(
            object_id=mt
        ).order_by('-date_created')
        self.assertEqual(mt_history.count(), 1)
        self.assertEqual(mt_history[0].probekey, probe_history[0])
        metric = poem_models.Metric.objects.get(name='argo.AMS-Check')
        self.assertEqual(metric.probekey, probe_history[0])
        metric_history = poem_models.TenantHistory.objects.filter(
            object_repr=metric.__str__()
        ).order_by('-date_created')
        self.assertEqual(metric_history.count(), 1)
        serialized_data = \
            json.loads(metric_history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['probekey'], ['ams-probe', '0.1.7'])

    def test_put_package_with_already_existing_name_and_version(self):
        data = {
            'id': self.package1.id,
            'name': 'nagios-plugins-globus',
            'version': '0.1.5',
            'use_present_version': False,
            'repos': ['repo-1 (CentOS 7)']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'Package with this name and version already exists.'}
        )

    def test_put_package_with_with_repo_without_tag(self):
        data = {
            'id': self.package1.id,
            'name': 'nagios-plugins-argo',
            'version': '0.1.12',
            'use_present_version': False,
            'repos': ['repo-1']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data, {'detail': 'You should specify YUM repo tag!'}
        )

    def test_put_package_with_with_nonexisting_repo(self):
        data = {
            'id': self.package1.id,
            'name': 'nagios-plugins-argo',
            'version': '0.1.12',
            'use_present_version': False,
            'repos': ['nonexisting (CentOS 7)']
        }
        content, content_type = encode_data(data)
        request = self.factory.put(self.url, content, content_type=content_type)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'detail': 'YUM repo not found.'}
        )

    def test_delete_package(self):
        self.assertEqual(admin_models.Package.objects.all().count(), 4)
        request = self.factory.delete(self.url + 'nagios-plugins-globus-0.1.5')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nagios-plugins-globus-0.1.5')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertRaises(
            admin_models.Package.DoesNotExist,
            admin_models.Package.objects.get,
            name='nagios-plugins-globus'
        )
        self.assertEqual(admin_models.Package.objects.all().count(), 3)

    def test_delete_package_with_associated_probe(self):
        request = self.factory.delete(self.url + 'nagios-plugins-argo-0.1.11')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nagios-plugins-argo-0.1.11')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'detail': 'You cannot delete package with associated probes!'}
        )

    def test_delete_nonexisting_package(self):
        request = self.factory.delete(self.url + 'nonexisting-0.1.1')
        force_authenticate(request, user=self.user)
        response = self.view(request, 'nonexisting-0.1.1')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {'detail': 'Package not found.'}
        )


class ListOSTagsAPIViewTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListOSTags.as_view()
        self.url = '/api/v2/internal/ostags/'
        self.user = CustUser.objects.create(username='testuser')

        admin_models.OSTag.objects.create(name='CentOS 6')
        admin_models.OSTag.objects.create(name='CentOS 7')

    def test_get_tags(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            [r for r in response.data],
            [
                'CentOS 6',
                'CentOS 7',
            ]
        )


class ListMetricTemplatesForImportTests(TenantTestCase):
    def setUp(self):
        self.factory = TenantRequestFactory(self.tenant)
        self.view = views.ListMetricTemplatesForImport.as_view()
        self.url = '/api/v2/internal/metrictemplates-import/'
        self.user = CustUser.objects.create_user(username='testuser')

        mtype1 = admin_models.MetricTemplateType.objects.create(name='Active')
        mtype2 = admin_models.MetricTemplateType.objects.create(name='Passive')

        tag1 = admin_models.OSTag.objects.create(name='CentOS 6')
        tag2 = admin_models.OSTag.objects.create(name='CentOS 7')

        repo1 = admin_models.YumRepo.objects.create(name='repo-1', tag=tag1)
        repo2 = admin_models.YumRepo.objects.create(name='repo-2', tag=tag2)

        package1 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.7'
        )
        package1.repos.add(repo1)

        package2 = admin_models.Package.objects.create(
            name='nagios-plugins-argo',
            version='0.1.11'
        )
        package2.repos.add(repo1, repo2)

        package3 = admin_models.Package.objects.create(
            name='nagios-plugins-nrpe',
            version='3.2.0'
        )
        package3.repos.add(repo1)

        package4 = admin_models.Package.objects.create(
            name='nagios-plugins-nrpe',
            version='3.2.1'
        )
        package4.repos.add(repo2)

        package5 = admin_models.Package.objects.create(
            name='sdc-nerc-sparql',
            version='1.0.1'
        )
        package5.repos.add(repo2)

        probe1 = admin_models.Probe.objects.create(
            name='ams-probe',
            package=package1,
            description='Probe is inspecting AMS service.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/nagios-plugins-argo',
            docurl='https://github.com/ARGOeu/nagios-plugins-argo/blob/master/'
                   'README.md'
        )

        probe2 = admin_models.Probe.objects.create(
            name='check_nrpe',
            package=package3,
            description='This is a plugin that is and is used to contact the '
                        'NRPE process on remote hosts.',
            comment='Initial version.',
            repository='https://github.com/NagiosEnterprises/nrpe',
            docurl='https://github.com/NagiosEnterprises/nrpe/blob/master/'
                   'CHANGELOG.md'
        )

        probe3 = admin_models.Probe.objects.create(
            name='sdc-nerq-sparq',
            package=package5,
            description='sparql endpoint nvs.',
            comment='Initial version.',
            repository='https://github.com/ARGOeu/sdc-nerc-spqrql',
            docurl='https://github.com/ARGOeu/sdc-nerc-spqrql'
        )

        probeversion1 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probe1.package = package2
        probe1.comment = 'Newer version.'
        probe1.save()

        probeversion2 = admin_models.ProbeHistory.objects.create(
            object_id=probe1,
            name=probe1.name,
            package=probe1.package,
            description=probe1.description,
            comment=probe1.comment,
            repository=probe1.repository,
            docurl=probe1.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Newer version.',
            version_user=self.user.username
        )

        probeversion3 = admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        probe2.package = package4
        probe2.comment = 'Newer version.'
        probe2.save()

        probeversion4 = admin_models.ProbeHistory.objects.create(
            object_id=probe2,
            name=probe2.name,
            package=probe2.package,
            description=probe2.description,
            comment=probe2.comment,
            repository=probe2.repository,
            docurl=probe2.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Newer version.',
            version_user=self.user.username
        )

        probeversion5 = admin_models.ProbeHistory.objects.create(
            object_id=probe3,
            name=probe3.name,
            package=probe3.package,
            description=probe3.description,
            comment=probe3.comment,
            repository=probe3.repository,
            docurl=probe3.docurl,
            date_created=datetime.datetime.now(),
            version_comment='Initial version.',
            version_user=self.user.username
        )

        metrictemplate1 = admin_models.MetricTemplate.objects.create(
            name='argo.AMS-Check',
            mtype=mtype1,
            probekey=probeversion1,
            probeexecutable='["ams-probe"]',
            config='["maxCheckAttempts 3", "timeout 60", '
                   '"path /usr/libexec/argo-monitoring/probes/argo", '
                   '"interval 5", "retryInterval 3"]',
            attribute='["argo.ams_TOKEN --token"]',
            flags='["OBSESS 1"]',
            parameter='["--project EGI"]'
        )

        self.mtversion1 = admin_models.MetricTemplateHistory.objects.create(
            object_id=metrictemplate1,
            name=metrictemplate1.name,
            mtype=metrictemplate1.mtype,
            probekey=metrictemplate1.probekey,
            probeexecutable=metrictemplate1.probeexecutable,
            config=metrictemplate1.config,
            attribute=metrictemplate1.attribute,
            dependency=metrictemplate1.dependency,
            flags=metrictemplate1.flags,
            files=metrictemplate1.files,
            parameter=metrictemplate1.parameter,
            fileparameter=metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Initial version.'
        )

        metrictemplate1.probekey = probeversion2
        metrictemplate1.save()

        self.mtversion2 = admin_models.MetricTemplateHistory.objects.create(
            object_id=metrictemplate1,
            name=metrictemplate1.name,
            mtype=metrictemplate1.mtype,
            probekey=metrictemplate1.probekey,
            probeexecutable=metrictemplate1.probeexecutable,
            config=metrictemplate1.config,
            attribute=metrictemplate1.attribute,
            dependency=metrictemplate1.dependency,
            flags=metrictemplate1.flags,
            files=metrictemplate1.files,
            parameter=metrictemplate1.parameter,
            fileparameter=metrictemplate1.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Newer version.'
        )

        metrictemplate2 = admin_models.MetricTemplate.objects.create(
            name='argo.EGI-Connectors-Check',
            mtype=mtype1,
            probekey=probeversion3,
            probeexecutable='["check_nrpe"]',
            config='["maxCheckAttempts 2", "timeout 60", '
                   '"path /usr/lib64/nagios/plugins", '
                   '"interval 720", "retryInterval 15"]',
            parameter='["-c check_connectors_egi"]'
        )

        self.mtversion3 = admin_models.MetricTemplateHistory.objects.create(
            object_id=metrictemplate2,
            name=metrictemplate2.name,
            mtype=metrictemplate2.mtype,
            probekey=metrictemplate2.probekey,
            probeexecutable=metrictemplate2.probeexecutable,
            config=metrictemplate2.config,
            attribute=metrictemplate2.attribute,
            dependency=metrictemplate2.dependency,
            flags=metrictemplate2.flags,
            files=metrictemplate2.files,
            parameter=metrictemplate2.parameter,
            fileparameter=metrictemplate2.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Initial version.'
        )

        metrictemplate2.probekey = probeversion4
        metrictemplate2.save()

        self.mtversion4 = admin_models.MetricTemplateHistory.objects.create(
            object_id=metrictemplate2,
            name=metrictemplate2.name,
            mtype=metrictemplate2.mtype,
            probekey=metrictemplate2.probekey,
            probeexecutable=metrictemplate2.probeexecutable,
            config=metrictemplate2.config,
            attribute=metrictemplate2.attribute,
            dependency=metrictemplate2.dependency,
            flags=metrictemplate2.flags,
            files=metrictemplate2.files,
            parameter=metrictemplate2.parameter,
            fileparameter=metrictemplate2.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Newer version.'
        )

        metrictemplate3 = admin_models.MetricTemplate.objects.create(
            name='org.apel.APEL-Pub',
            flags='["OBSESS 1", "PASSIVE 1"]',
            mtype=mtype2
        )

        self.mtversion5 = admin_models.MetricTemplateHistory.objects.create(
            object_id=metrictemplate3,
            name=metrictemplate3.name,
            mtype=metrictemplate3.mtype,
            probekey=metrictemplate3.probekey,
            probeexecutable=metrictemplate3.probeexecutable,
            config=metrictemplate3.config,
            attribute=metrictemplate3.attribute,
            dependency=metrictemplate3.dependency,
            flags=metrictemplate3.flags,
            files=metrictemplate3.files,
            parameter=metrictemplate3.parameter,
            fileparameter=metrictemplate3.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Initial version.'
        )

        metrictemplate4 = admin_models.MetricTemplate.objects.create(
            name='eu.seadatanet.org.nerc-sparql-check',
            mtype=mtype1,
            probekey=probeversion5,
            probeexecutable='sdc-nerq-sparql.sh',
            config='["interval 15", "maxCheckAttempts 3", '
                   '"path /usr/libexec/argo-monitoring/probes/'
                   'sdc-nerc-sparql/", "retryInterval 3", "timeout 15"]',
            attribute='["eu.seadatanet.org.nerc-sparql_URL -H"]',
            flags='["OBSESS 1", "PNP 1"]'
        )

        self.mtversion6 = admin_models.MetricTemplateHistory.objects.create(
            object_id=metrictemplate4,
            name=metrictemplate4.name,
            mtype=metrictemplate4.mtype,
            probekey=metrictemplate4.probekey,
            probeexecutable=metrictemplate4.probeexecutable,
            config=metrictemplate4.config,
            attribute=metrictemplate4.attribute,
            dependency=metrictemplate4.dependency,
            flags=metrictemplate4.flags,
            files=metrictemplate4.files,
            parameter=metrictemplate4.parameter,
            fileparameter=metrictemplate4.fileparameter,
            date_created=datetime.datetime.now(),
            version_user=self.user.username,
            version_comment='Initial version.'
        )

    def test_get_metrictemplates_for_import_fail_if_no_auth(self):
        request = self.factory.get(self.url)
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_metrictemplates_for_import_all(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(
            response.data,
            [
                {
                    'name': 'argo.AMS-Check',
                    'mtype': 'Active',
                    'ostag': ['CentOS 6', 'CentOS 7'],
                    'probeversion': 'ams-probe (0.1.11)',
                    'centos6_probeversion': 'ams-probe (0.1.11)',
                    'centos7_probeversion': 'ams-probe (0.1.11)'
                },
                {
                    'name': 'argo.EGI-Connectors-Check',
                    'mtype': 'Active',
                    'ostag': ['CentOS 6', 'CentOS 7'],
                    'probeversion': 'check_nrpe (3.2.1)',
                    'centos6_probeversion': 'check_nrpe (3.2.0)',
                    'centos7_probeversion': 'check_nrpe (3.2.1)'
                },
                {
                    'name': 'eu.seadatanet.org.nerc-sparql-check',
                    'mtype': 'Active',
                    'ostag': ['CentOS 7'],
                    'probeversion': 'sdc-nerq-sparq (1.0.1)',
                    'centos6_probeversion': '',
                    'centos7_probeversion': 'sdc-nerq-sparq (1.0.1)'
                },
                {
                    'name': 'org.apel.APEL-Pub',
                    'mtype': 'Passive',
                    'ostag': ['CentOS 6', 'CentOS 7'],
                    'probeversion': '',
                    'centos6_probeversion': '',
                    'centos7_probeversion': ''
                }
            ]
        )


class SyncWebApiTests(TenantTestCase):
    def setUp(self):
        ct_mp = ContentType.objects.get_for_model(poem_models.MetricProfiles)
        MyAPIKey.objects.create(
            name='WEB-API',
            token='mocked_token'
        )

        self.mp1 = poem_models.MetricProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.mp2 = poem_models.MetricProfiles.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.mp1],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'metricinstances': [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['APEL', 'org.apel.APEL-Sync']
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.mp1.id,
            serialized_data=json.dumps(data),
            object_repr=self.mp1.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=ct_mp
        )

        data = json.loads(
            serializers.serialize(
                'json', [self.mp2],
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        )
        data[0]['fields'].update({
            'metricinstances': [
                ['AMGA', 'org.nagios.SAML-SP'],
                ['APEL', 'org.apel.APEL-Pub'],
                ['APEL', 'org.apel.APEL-Sync']
            ]
        })

        poem_models.TenantHistory.objects.create(
            object_id=self.mp2.id,
            serialized_data=json.dumps(data),
            object_repr=self.mp2.__str__(),
            comment='Initial version.',
            user='testuser',
            content_type=ct_mp
        )

        self.aggr1 = poem_models.Aggregation.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.aggr2 = poem_models.Aggregation.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.tp1 = poem_models.ThresholdsProfiles.objects.create(
            name='TEST_PROFILE',
            apiid='00000000-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

        self.tp2 = poem_models.ThresholdsProfiles.objects.create(
            name='ANOTHER-PROFILE',
            apiid='12341234-oooo-kkkk-aaaa-aaeekkccnnee',
            groupname='EGI'
        )

    @patch('requests.get', side_effect=mocked_web_api_request)
    def test_sync_webapi_metricprofiles(self, func):
        self.assertEqual(poem_models.MetricProfiles.objects.all().count(), 2)
        sync_webapi('metric_profiles', poem_models.MetricProfiles)
        self.assertEqual(poem_models.MetricProfiles.objects.all().count(), 2)
        self.assertEqual(
            poem_models.MetricProfiles.objects.get(name='TEST_PROFILE'),
            self.mp1
        )
        self.assertRaises(
            poem_models.MetricProfiles.DoesNotExist,
            poem_models.MetricProfiles.objects.get,
            name='ANOTHER-PROFILE'
        )
        self.assertEqual(
            poem_models.TenantHistory.objects.filter(
                object_id=self.mp2.id
            ).count(), 0
        )
        self.assertTrue(
            poem_models.MetricProfiles.objects.get(name='NEW_PROFILE')
        )
        history = poem_models.TenantHistory.objects.filter(
            object_repr='NEW_PROFILE'
        )
        self.assertEqual(history.count(), 1)
        self.assertEqual(history[0].comment, 'Initial version.')
        serialized_data = json.loads(history[0].serialized_data)[0]['fields']
        self.assertEqual(serialized_data['name'], 'NEW_PROFILE')
        self.assertEqual(
            serialized_data['apiid'], '11110000-aaaa-kkkk-aaaa-aaeekkccnnee'
        )
        self.assertEqual(
            serialized_data['metricinstances'],
            [['dg.3GBridge', 'eu.egi.cloud.Swift-CRUD']]
        )

    @patch('requests.get', side_effect=mocked_web_api_request)
    def test_sync_webapi_aggregationprofiles(self, func):
        self.assertEqual(poem_models.Aggregation.objects.all().count(), 2)
        sync_webapi('aggregation_profiles', poem_models.Aggregation)
        self.assertEqual(poem_models.Aggregation.objects.all().count(), 2)
        self.assertEqual(
            poem_models.Aggregation.objects.get(name='TEST_PROFILE'), self.aggr1
        )
        self.assertRaises(
            poem_models.Aggregation.DoesNotExist,
            poem_models.Aggregation.objects.get,
            name='ANOTHER-PROFILE'
        )
        self.assertTrue(poem_models.Aggregation.objects.get(name='NEW_PROFILE'))

    @patch('requests.get', side_effect=mocked_web_api_request)
    def test_sync_webapi_thresholdsprofile(self, func):
        self.assertEqual(
            poem_models.ThresholdsProfiles.objects.all().count(), 2
        )
        sync_webapi('thresholds_profiles', poem_models.ThresholdsProfiles)
        self.assertEqual(
            poem_models.ThresholdsProfiles.objects.all().count(), 2
        )
        self.assertEqual(
            poem_models.ThresholdsProfiles.objects.get(name='TEST_PROFILE'),
            self.tp1
        )
        self.assertRaises(
            poem_models.ThresholdsProfiles.DoesNotExist,
            poem_models.ThresholdsProfiles.objects.get,
            name='ANOTHER-PROFILE'
        )


class CommentsTests(TenantTestCase):
    def test_new_comment_with_objects_change(self):
        comment = '[{"changed": {"fields": ["config"], ' \
                  '"object": ["maxCheckAttempts", "path", "timeout"]}}, ' \
                  '{"changed": {"fields": ["attribute"], ' \
                  '"object": ["attribute-key1", "attribute-key2"]}}, ' \
                  '{"changed": {"fields": ["dependency"], ' \
                  '"object": ["dependency-key"]}}]'
        self.assertEqual(
            new_comment(comment),
            'Changed config fields "maxCheckAttempts", "path" and "timeout". '
            'Changed attribute fields "attribute-key1" and "attribute-key2". '
            'Changed dependency field "dependency-key".'
        )

    def test_new_comment_with_objects_add(self):
        comment = '[{"added": {"fields": ["config"], ' \
                  '"object": ["maxCheckAttempts", "path", "timeout"]}}, ' \
                  '{"added": {"fields": ["attribute"], ' \
                  '"object": ["attribute-key1", "attribute-key2"]}}, ' \
                  '{"added": {"fields": ["dependency"], ' \
                  '"object": ["dependency-key"]}}]'
        self.assertEqual(
            new_comment(comment),
            'Added config fields "maxCheckAttempts", "path" and "timeout". '
            'Added attribute fields "attribute-key1" and "attribute-key2". '
            'Added dependency field "dependency-key".'
        )

    def test_new_comment_with_objects_delete(self):
        comment = '[{"deleted": {"fields": ["config"], ' \
                  '"object": ["maxCheckAttempts", "path", "timeout"]}}, ' \
                  '{"deleted": {"fields": ["attribute"], ' \
                  '"object": ["attribute-key1", "attribute-key2"]}}, ' \
                  '{"deleted": {"fields": ["dependency"], ' \
                  '"object": ["dependency-key"]}}]'
        self.assertEqual(
            new_comment(comment),
            'Deleted config fields "maxCheckAttempts", "path" and "timeout". '
            'Deleted attribute fields "attribute-key1" and "attribute-key2". '
            'Deleted dependency field "dependency-key".'
        )

    def test_new_comment_with_fields(self):
        comment = '[{"added": {"fields": ["docurl", "comment"]}}, ' \
                  '{"changed": {"fields": ["name", "probeexecutable", ' \
                  '"group"]}}, ' \
                  '{"deleted": {"fields": ["version", "description"]}}]'
        self.assertEqual(
            new_comment(comment),
            'Added docurl and comment. '
            'Changed name, probeexecutable and group. '
            'Deleted version and description.'
        )

    def test_new_comment_initial(self):
        comment = 'Initial version.'
        self.assertEqual(new_comment(comment), 'Initial version.')

    def test_new_comment_no_changes(self):
        comment = '[]'
        self.assertEqual(new_comment(comment), 'No fields changed.')

    def test_new_comment_for_thresholds_profiles_rules_field(self):
        comment = '[{"changed": {"fields": ["rules"], ' \
                  '"object": ["metricA"]}}, ' \
                  '{"deleted": {"fields": ["rules"], ' \
                  '"object": ["metricB"]}}, ' \
                  '{"added": {"fields": ["rules"], "object": ["metricC"]}}]'
        self.assertEqual(
            new_comment(comment),
            'Changed rule for metric "metricA". '
            'Deleted rule for metric "metricB". '
            'Added rule for metric "metricC".'
        )

    def test_new_comment_for_metric_profile_metricinstances(self):
        comment = '[{"added": {"fields": ["metricinstances"], ' \
                  '"object": ["ARC-CE", "org.nordugrid.ARC-CE-IGTF"]}}, ' \
                  '{"deleted": {"fields": ["metricinstances"], ' \
                  '"object": ["APEL", "org.apel.APEL-Sync"]}}]'
        self.assertEqual(
            new_comment(comment),
            'Added service-metric instance tuple '
            '(ARC-CE, org.nordugrid.ARC-CE-IGTF). '
            'Deleted service-metric instance tuple '
            '(APEL, org.apel.APEL-Sync).'
        )
