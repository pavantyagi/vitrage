# Copyright 2016 - Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from oslo_log import log as logging

from vitrage.common.constants import EdgeLabels
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import SynchronizerProperties as SyncProps
from vitrage.common.constants import VertexProperties as VProps
from vitrage.synchronizer.plugins.cinder.volume import CINDER_VOLUME_PLUGIN
from vitrage.synchronizer.plugins.cinder.volume.transformer \
    import CinderVolumeTransformer
from vitrage.synchronizer.plugins.nova.instance import NOVA_INSTANCE_PLUGIN
from vitrage.synchronizer.plugins.nova.instance.transformer \
    import InstanceTransformer
from vitrage.synchronizer.plugins.transformer_base import TransformerBase
from vitrage.tests import base
from vitrage.tests.mocks import mock_syncronizer as mock_sync

LOG = logging.getLogger(__name__)


class TestCinderVolumeTransformer(base.BaseTest):

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.transformers = {}
        cls.transformers[CINDER_VOLUME_PLUGIN] = \
            CinderVolumeTransformer(cls.transformers)
        cls.transformers[NOVA_INSTANCE_PLUGIN] = \
            InstanceTransformer(cls.transformers)

    def test_create_placeholder_vertex(self):
        LOG.debug('Cinder Volume transformer test: Create placeholder '
                  'vertex')

        # Tests setup
        volume_id = 'Instance123'
        timestamp = datetime.datetime.utcnow()
        properties = {
            VProps.ID: volume_id,
            VProps.SAMPLE_TIMESTAMP: timestamp
        }
        transformer = CinderVolumeTransformer(self.transformers)

        # Test action
        placeholder = transformer.create_placeholder_vertex(**properties)

        # Test assertions
        observed_id_values = placeholder.vertex_id.split(
            TransformerBase.KEY_SEPARATOR)
        expected_id_values = transformer._key_values(CINDER_VOLUME_PLUGIN,
                                                     volume_id)
        self.assertEqual(tuple(observed_id_values), expected_id_values)

        observed_time = placeholder.get(VProps.SAMPLE_TIMESTAMP)
        self.assertEqual(observed_time, timestamp)

        observed_type = placeholder.get(VProps.TYPE)
        self.assertEqual(observed_type, CINDER_VOLUME_PLUGIN)

        observed_entity_id = placeholder.get(VProps.ID)
        self.assertEqual(observed_entity_id, volume_id)

        observed_category = placeholder.get(VProps.CATEGORY)
        self.assertEqual(observed_category, EntityCategory.RESOURCE)

        is_placeholder = placeholder.get(VProps.IS_PLACEHOLDER)
        self.assertEqual(is_placeholder, True)

    def test_key_values(self):
        LOG.debug('Cinder Volume transformer test: get key values')

        # Test setup
        volume_type = CINDER_VOLUME_PLUGIN
        volume_id = '12345'
        transformer = CinderVolumeTransformer(self.transformers)

        # Test action
        observed_key_fields = transformer._key_values(volume_type,
                                                      volume_id)

        # Test assertions
        self.assertEqual(EntityCategory.RESOURCE, observed_key_fields[0])
        self.assertEqual(CINDER_VOLUME_PLUGIN, observed_key_fields[1])
        self.assertEqual(volume_id, observed_key_fields[2])

    def test_snapshot_transform(self):
        LOG.debug('Cinder Volume transformer test: transform entity event '
                  'snapshot')

        # Test setup
        spec_list = mock_sync.simple_volume_generators(3, 7, 7)
        static_events = mock_sync.generate_random_events_list(spec_list)

        for event in static_events:
            # Test action
            wrapper = self.transformers[CINDER_VOLUME_PLUGIN].transform(event)

            # Test assertions
            vertex = wrapper.vertex
            self._validate_volume_vertex_props(vertex, event)

            neighbors = wrapper.neighbors
            self._validate_neighbors(neighbors, vertex.vertex_id, event)

    def _validate_volume_vertex_props(self, vertex, event):
        sync_mode = event[SyncProps.SYNC_MODE]

        self.assertEqual(EntityCategory.RESOURCE, vertex[VProps.CATEGORY])
        self.assertEqual(event[SyncProps.SYNC_TYPE], vertex[VProps.TYPE])
        self.assertEqual(
            event[CinderVolumeTransformer.VOLUME_ID[sync_mode][0]],
            vertex[VProps.ID])
        self.assertEqual(event[SyncProps.SAMPLE_DATE],
                         vertex[VProps.SAMPLE_TIMESTAMP])
        self.assertEqual(
            event[CinderVolumeTransformer.VOLUME_NAME[sync_mode][0]],
            vertex[VProps.NAME])
        self.assertEqual(
            event[CinderVolumeTransformer.VOLUME_STATE[sync_mode][0]],
            vertex[VProps.STATE])
        self.assertFalse(vertex[VProps.IS_PLACEHOLDER])
        self.assertFalse(vertex[VProps.IS_DELETED])

    def _validate_neighbors(self, neighbors, volume_vertex_id, event):
        instance_counter = 0

        for neighbor in neighbors:
            self._validate_instance_neighbor(
                neighbor,
                event['attachments'][0]['server_id'],
                volume_vertex_id)
            instance_counter += 1

        self.assertEqual(1,
                         instance_counter,
                         'Zone can belongs to only one Node')

    def _validate_instance_neighbor(self,
                                    instance_neighbor,
                                    instance_id,
                                    volume_vertex_id):
        # validate neighbor vertex
        self.assertEqual(EntityCategory.RESOURCE,
                         instance_neighbor.vertex[VProps.CATEGORY])
        self.assertEqual(NOVA_INSTANCE_PLUGIN,
                         instance_neighbor.vertex[VProps.TYPE])
        self.assertEqual(instance_id, instance_neighbor.vertex[VProps.ID])
        self.assertTrue(instance_neighbor.vertex[VProps.IS_PLACEHOLDER])
        self.assertFalse(instance_neighbor.vertex[VProps.IS_DELETED])

        # Validate neighbor edge
        edge = instance_neighbor.edge
        self.assertEqual(edge.target_id, instance_neighbor.vertex.vertex_id)
        self.assertEqual(edge.source_id, volume_vertex_id)
        self.assertEqual(edge.label, EdgeLabels.ATTACHED)
