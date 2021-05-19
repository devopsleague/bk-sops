# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.translation import ugettext_lazy as _

from api.collections.nodeman import BKNodeManClient
from pipeline.component_framework.component import Component

from pipeline.core.flow.io import (
    IntItemSchema,
    StringItemSchema,
    ArrayItemSchema,
    ObjectItemSchema,
)

from gcloud.conf import settings
from gcloud.utils.ip import get_ip_by_regex
from pipeline_plugins.components.utils.sites.open.utils import get_nodeman_job_url

from ..base import NodeManBaseService, get_host_id_by_inner_ip

__group_name__ = _("节点管理(Nodeman)")


INSTALL_TYPE = ["MAIN_INSTALL_PLUGIN"]


class NodemanPluginOperateService(NodeManBaseService):
    def inputs_format(self):
        return [
            self.InputItem(
                name=_("业务 ID"),
                key="bk_biz_id",
                type="int",
                schema=IntItemSchema(description=_("当前操作所属的 CMDB 业务 ID")),
            ),
            self.InputItem(
                name=_("插件操作信息"),
                key="nodeman_plugin_operate",
                type="object",
                schema=ObjectItemSchema(
                    description=_("插件操作内容"),
                    property_schemas={
                        "nodeman_op_type": StringItemSchema(description=_("插件操作类型")),
                        "nodeman_plugin": StringItemSchema(description=_("插件名称")),
                        "nodeman_plugin_version": StringItemSchema(description=_("插件版本")),
                        "install_config": ArrayItemSchema(
                            description=_("安装操作参数"),
                            item_schema=StringItemSchema(
                                description=_("安装选项，nodeman_op_type值为MAIN_INSTALL_PLUGIN时可填"),
                                enum=["keep_config", "no_restart"],
                            ),
                        ),
                    },
                ),
            ),
            self.InputItem(
                name=_("主机信息"),
                key="nodeman_host_info",
                type="object",
                schema=ObjectItemSchema(
                    description=_("主机信息内容"),
                    property_schemas={
                        "nodeman_host_input_type": StringItemSchema(
                            description=_("主机填写方式"), enum=["host_ip", "host_id"]
                        ),
                        "nodeman_bk_cloud_id": IntItemSchema(description=_("主机所在云区域 ID")),
                        "nodeman_host_ip": StringItemSchema(
                            description=_("主机ip,多个以英文','分隔，nodeman_host_input_type值为host_ip时必填")
                        ),
                        "nodeman_host_id": StringItemSchema(
                            description=_("主机id,多个以英文','分隔，nodeman_host_input_type值为host_id时必填")
                        ),
                    },
                ),
            ),
        ]

    def outputs_format(self):
        outputs_format = super(NodemanPluginOperateService, self).outputs_format()
        outputs_format.extend(
            [
                self.OutputItem(
                    name=_("任务链接"),
                    key="job_url",
                    type="string",
                    schema=StringItemSchema(description=_("任务链接")),
                ),
            ]
        )
        return outputs_format

    def execute(self, data, parent_data):
        executor = parent_data.inputs.executor
        client = BKNodeManClient(username=executor)
        bk_biz_id = data.inputs.biz_cc_id

        nodeman_op_target = data.inputs.nodeman_plugin_operate
        op_type = nodeman_op_target.get("nodeman_op_type", "")
        plugin = nodeman_op_target.get("nodeman_plugin", "")
        plugin_version = nodeman_op_target.get("nodeman_plugin_version", "")
        install_config = nodeman_op_target.get("install_config", [])

        host_info = data.inputs.nodeman_host_info
        input_type = host_info.get("nodeman_host_input_type", None)

        if not input_type:
            data.set_outputs("ex_data", _("请选择填写方式"))
            return False
        if input_type == "host_ip":
            bk_cloud_id = host_info.get("nodeman_bk_cloud_id", None)
            ip_list = get_ip_by_regex(host_info.get("nodeman_host_ip", ""))
            host_id_dict = get_host_id_by_inner_ip(executor, self.logger, bk_cloud_id, bk_biz_id, ip_list)

            # 过滤出未查询到host_id的ip
            no_host_id_ip = list(set(ip_list).difference(set(host_id_dict.keys())))
            if no_host_id_ip:
                data.set_outputs("ex_data", _("获取bk_host_id失败:{},请确认云区域是否正确".format(",".join(no_host_id_ip))))
                return False
            host = list(host_id_dict.values())
        else:
            host = host_info.get("nodeman_host_id", "").strip().split(",")

        # 拼装参数
        params = {
            "job_type": op_type,
            "bk_biz_id": [bk_biz_id],
            "bk_host_id": host,
            "plugin_params": {"name": plugin, "version": plugin_version},
        }

        if op_type == "MAIN_INSTALL_PLUGIN" and install_config:
            if "keep_config" in install_config:
                params["plugin_params"].update({"keep_config": 1})
            elif "no_restart" in install_config:
                params["plugin_params"].update({"no_restart": 1})

        result = client.plugin_operate(params)

        if result["result"]:
            job_id = result["data"].get("job_id", None)
            data.outputs.job_url = [get_nodeman_job_url(job_id, host_id) for host_id in host]

        return self.get_job_result(result, data, "plugin_operate", params)


class NodemanPluginOperateComponent(Component):
    name = _("插件操作")
    code = "nodeman_plugin_operate"
    bound_service = NodemanPluginOperateService
    form = "%scomponents/atoms/nodeman/plugin_operate/v1_0.js" % settings.STATIC_URL
    version = "v1.0"
