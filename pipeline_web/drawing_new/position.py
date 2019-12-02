# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from pipeline.core.constants import PE

from pipeline_web.drawing_new.constants import (
    MIN_LEN,
    FLOW_ARROW,
    PIPELINE_ELEMENT_TO_WEB,
    PIPELINE_WEB_TO_ELEMENT,
    DUMMY_NODE_TYPE
)


def position(pipeline,
             orders,
             activity_size,
             event_size,
             gateway_size,
             start,
             canvas_width,
             more_flows=None):
    """
    @summary：将后台 pipeline tree 转换成带前端 location、line 画布信息的数据
    @param pipeline: 后台流程树
    @param orders: 层级和同一层级内节点顺序
    @param activity_size: 任务节点长宽，如 (150, 42)
    @param event_size: 事件节点长宽，如 (40, 40)
    @param gateway_size: 网关节点长宽，如 (36, 36)
    @param start: 开始节点绝对定位X、Y轴坐标
    @param canvas_width: 画布最大宽度
    @param more_flows: 额外需要获取位置信息的连线，如反向边、被替换的长边
    @return:
    """
    # 节点之间的平均距离
    shift_x = max(activity_size[0], event_size[0], gateway_size[0]) * 1.2
    shift_y = max(activity_size[1], event_size[1], gateway_size[1]) * 2
    # 开始/结束节点纵坐标偏差
    event_shift_y = (activity_size[1] - event_size[1]) * 0.5
    # 网关节点纵坐标偏差
    gateway_shift_y = (activity_size[1] - gateway_size[1]) * 0.5
    pipeline_element_shift_y = {
        DUMMY_NODE_TYPE: 0,
        PE.ServiceActivity: 0,
        PE.SubProcess: 0,
        PE.EmptyStartEvent: event_shift_y,
        PE.EmptyEndEvent: event_shift_y,
        PE.ExclusiveGateway: gateway_shift_y,
        PE.ParallelGateway: gateway_shift_y,
        PE.ConvergeGateway: gateway_shift_y
    }

    min_rk = min(list(orders.keys()))
    max_rk = max(list(orders.keys()))
    # 先分配节点位置
    locations = {}
    rank_x, rank_y = start
    new_line_y = []
    for rk in range(min_rk, max_rk + MIN_LEN, MIN_LEN):
        layer_nodes = orders[rk]
        # 当前 rank 首个节点位置
        order_x, order_y = rank_x, rank_y
        for node_id in layer_nodes:
            if node_id in pipeline['all_nodes']:
                node = pipeline['all_nodes'][node_id]
                locations[node[PE.id]] = {
                    'id': node[PE.id],
                    'type': PIPELINE_ELEMENT_TO_WEB.get(node[PE.type], node[PE.type]),
                    'name': node.get(PE.name, ''),
                    'status': '',
                    'x': int(order_x),
                    'y': int(order_y + pipeline_element_shift_y[node[PE.type]])
                }
            order_y += shift_y
        new_line_y.append(order_y - shift_y)
        rank_x += shift_x
        # 1)宽度超出画布宽度 canvas_width 2)无分支 3)下一个节点非结束节点 ——> 换行
        if rank_x > canvas_width and len(layer_nodes) == 1 and rk < max_rk - MIN_LEN:
            rank_x = start[0]
            rank_y += max(new_line_y)
            new_line_y = []

    flows = {}
    flows.update(pipeline[PE.flows])
    if isinstance(more_flows, dict):
        flows.update(more_flows)
    lines = position_flows(flows, locations, pipeline_element_shift_y, start[0], shift_y)
    return locations, lines


def position_flows(flows, locations, pipeline_element_shift_y, start_x, shift_y):
    """
    @summary: 分配连线端点
    @param flows:
    @param locations:
    @param pipeline_element_shift_y:
    @param start_x: 画布最左侧
    @param shift_y: 画布默认行距
    @return:
    """
    lines = {}
    for flow_id, flow in flows.items():
        source_arrow, target_arrow = arrow_flow(flow, locations, pipeline_element_shift_y)
        lines[flow_id] = {
            'id': flow_id,
            'source': {
                'arrow': source_arrow,
                'id': flow[PE.source]
            },
            'target': {
                'arrow': target_arrow,
                'id': flow[PE.target]
            }
        }
        source_location = locations[flow[PE.source]]
        target_location = locations[flow[PE.target]]
        # 终点是每行起始位置，说明有换行，每次换行线段需要设置线段比例保证下折线与下一行距离为单行间距
        if target_location['x'] == start_x:
            lines[flow_id]['midpoint'] = 1 - shift_y * 0.5 / (target_location['y'] - source_location['y'])
    return lines


def arrow_flow(flow, locations, pipeline_element_shift_y):
    """
    @summary: 根据 flow 起始点相对位置决定 flow 两端连线端点位置
    @param flow:
    @param locations:
    @param pipeline_element_shift_y:
    @return:
    """
    source_location = locations[flow[PE.source]]
    target_location = locations[flow[PE.target]]

    source_location_x = source_location['x']
    source_shift_y = pipeline_element_shift_y[PIPELINE_WEB_TO_ELEMENT[source_location['type']]]
    source_location_y = source_location['y'] - source_shift_y

    target_location_x = target_location['x']
    target_shift_y = pipeline_element_shift_y[PIPELINE_WEB_TO_ELEMENT[target_location['type']]]
    target_location_y = target_location['y'] - target_shift_y

    # 起点在终点左侧
    if source_location_x < target_location_x:
        # 并且起点在终点上侧，一般是发起分支
        if source_location_y < target_location_y:
            source_arrow = FLOW_ARROW['bottom']
            target_arrow = FLOW_ARROW['left']
        # 并且起点在终点下侧，一般是汇聚分支
        elif source_location_y > target_location_y:
            source_arrow = FLOW_ARROW['right']
            target_arrow = FLOW_ARROW['bottom']
        # 正常顺序流
        else:
            source_arrow = FLOW_ARROW['right']
            target_arrow = FLOW_ARROW['left']
    # 起点在终点右侧
    elif source_location_x > target_location_x:
        # 并且起点在终点上侧，一般是换行
        if source_location_y < target_location_y:
            source_arrow = FLOW_ARROW['right']
            target_arrow = FLOW_ARROW['left']
        # 并且起点在终点下侧，一般是打回流程
        elif source_location_y > target_location_y:
            source_arrow = FLOW_ARROW['left']
            target_arrow = FLOW_ARROW['bottom']
        else:
            source_arrow = FLOW_ARROW['left']
            target_arrow = FLOW_ARROW['right']
    # 起点和终点在同一横坐标上
    else:
        if source_location_y < target_location_y:
            source_arrow = FLOW_ARROW['bottom']
            target_arrow = FLOW_ARROW['top']
        elif source_location_y > target_location_y:
            source_arrow = FLOW_ARROW['top']
            target_arrow = FLOW_ARROW['bottom']
        # 自环边，目前还不会出现这种流程
        else:
            source_arrow = FLOW_ARROW['right']
            target_arrow = FLOW_ARROW['bottom']
    return source_arrow, target_arrow
