import datetime

from django.db import IntegrityError

import json

from Poem.api.views import NotFound
from Poem.helpers.history_helpers import create_history, update_comment
from Poem.poem import models as poem_models
from Poem.poem_super_admin import models as admin_models
from Poem.tenants.models import Tenant

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from tenant_schemas.utils import schema_context, get_public_schema_name


class ListProbes(APIView):
    authentication_classes = (SessionAuthentication,)

    def get(self, request, name=None):
        if name:
            try:
                probe = admin_models.Probe.objects.get(name=name)

                if probe.datetime:
                    probe_datetime = datetime.datetime.strftime(
                        probe.datetime, '%Y-%m-%dT%H:%M:%S.%f'
                    )
                else:
                    probe_datetime = ''

                result = dict(
                    id=probe.id,
                    name=probe.name,
                    version=probe.package.version,
                    package=probe.package.__str__(),
                    docurl=probe.docurl,
                    description=probe.description,
                    comment=probe.comment,
                    repository=probe.repository,
                    user=probe.user,
                    datetime=probe_datetime
                )

                return Response(result)

            except admin_models.Probe.DoesNotExist:
                raise NotFound(status=404, detail='Probe not found')

        else:
            probes = admin_models.Probe.objects.all()

            results = []
            for probe in probes:
                # number of probe revisions
                nv = admin_models.ProbeHistory.objects.filter(
                    object_id=probe
                ).count()

                results.append(
                    dict(
                        name=probe.name,
                        version=probe.package.version,
                        package=probe.package.__str__(),
                        docurl=probe.docurl,
                        description=probe.description,
                        comment=probe.comment,
                        repository=probe.repository,
                        nv=nv
                    )
                )

            results = sorted(results, key=lambda k: k['name'].lower())

            return Response(results)

    def put(self, request):
        schemas = list(
            Tenant.objects.all().values_list('schema_name', flat=True)
        )
        schemas.remove(get_public_schema_name())

        probe = admin_models.Probe.objects.get(id=request.data['id'])
        old_name = probe.name
        package_name = request.data['package'].split(' ')[0]
        package_version = request.data['package'].split(' ')[1][1:-1]
        package = admin_models.Package.objects.get(
            name=package_name, version=package_version
        )
        old_version = probe.package.version

        try:
            if package.version != old_version:
                probe.name = request.data['name']
                probe.package = package
                probe.repository = request.data['repository']
                probe.docurl = request.data['docurl']
                probe.description = request.data['description']
                probe.comment = request.data['comment']
                probe.user = request.user.username

                probe.save()
                create_history(probe, probe.user)

                if request.data['update_metrics'] in [True, 'true', 'True']:
                    metrictemplates = \
                        admin_models.MetricTemplate.objects.filter(
                            probekey__name=old_name,
                            probekey__package__version=old_version
                        )

                    for metrictemplate in metrictemplates:
                        metrictemplate.probekey = \
                            admin_models.ProbeHistory.objects.get(
                                name=probe.name,
                                package__version=probe.package.version
                            )
                        metrictemplate.save()
                        create_history(metrictemplate, request.user.username)

            else:
                history = admin_models.ProbeHistory.objects.filter(
                    name=old_name, package__version=old_version
                )
                probekey = history[0]
                new_data = {
                            'name': request.data['name'],
                            'package': package,
                            'description': request.data['description'],
                            'comment': request.data['comment'],
                            'repository': request.data['repository'],
                            'docurl': request.data['docurl'],
                            'user': request.user.username
                        }
                admin_models.Probe.objects.filter(pk=probe.id).update(
                    **new_data
                )

                del new_data['user']
                new_data.update({
                    'version_comment': update_comment(
                        admin_models.Probe.objects.get(
                            id=request.data['id']
                        )
                    )
                })
                history.update(**new_data)

                # update Metric history in case probekey name has changed:
                if request.data['name'] != old_name:
                    for schema in schemas:
                        with schema_context(schema):
                            metrics = poem_models.Metric.objects.filter(
                                probekey=probekey
                            )

                            for metric in metrics:
                                vers = poem_models.TenantHistory.objects.filter(
                                    object_id=metric.id
                                )

                                for ver in vers:
                                    serialized_data = json.loads(
                                        ver.serialized_data
                                    )

                                    serialized_data[0]['fields']['probekey'] = \
                                        [request.data['name'],
                                         package.version]

                                    ver.serialized_data = json.dumps(
                                        serialized_data
                                    )
                                    ver.save()

            return Response(status=status.HTTP_201_CREATED)

        except IntegrityError:
            return Response(
                {'detail': 'Probe with this name already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def post(self, request):
        package_name = request.data['package'].split(' ')[0]
        package_version = request.data['package'].split(' ')[1][1:-1]
        try:
            probe = admin_models.Probe.objects.create(
                name=request.data['name'],
                package=admin_models.Package.objects.get(
                    name=package_name, version=package_version
                ),
                repository=request.data['repository'],
                docurl=request.data['docurl'],
                description=request.data['description'],
                comment=request.data['comment'],
                user=request.user.username,
                datetime=datetime.datetime.now()
            )

            if request.data['cloned_from']:
                clone = admin_models.Probe.objects.get(
                    id=request.data['cloned_from']
                )
                comment = 'Derived from {} ({}).'.format(
                    clone.name, clone.package.version
                )
                create_history(probe, probe.user, comment=comment)

            else:
                create_history(probe, probe.user)

            return Response(status=status.HTTP_201_CREATED)

        except IntegrityError:
            return Response({'detail': 'Probe with this name already exists.'},
                            status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, name=None):
        schemas = list(
            Tenant.objects.all().values_list('schema_name', flat=True)
        )
        schemas.remove(get_public_schema_name())
        if name:
            try:
                probe = admin_models.Probe.objects.get(name=name)
                mt = admin_models.MetricTemplate.objects.filter(
                    probekey=admin_models.ProbeHistory.objects.get(
                        name=probe.name, package__version=probe.package.version
                    )
                )
                if len(mt) == 0:
                    for schema in schemas:
                        # need to iterate through schemas because of foreign
                        # key in Metric model
                        with schema_context(schema):
                            admin_models.ProbeHistory.objects.filter(
                                object_id=probe
                            ).delete()
                    probe.delete()
                    return Response(status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response(
                        {'detail': 'You cannot delete Probe that is associated '
                                   'to metric templates!'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            except admin_models.Probe.DoesNotExist:
                raise NotFound(status=404, detail='Probe not found')

        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
