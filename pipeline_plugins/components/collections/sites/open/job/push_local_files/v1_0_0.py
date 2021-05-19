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

import traceback
from functools import partial

from django.utils.translation import ugettext_lazy as _

from pipeline.component_framework.component import Component
from pipeline_plugins.components.collections.sites.open.job import JobService
from pipeline_plugins.components.utils import (
    cc_get_ips_info_by_str,
    get_job_instance_url,
    get_node_callback_url,
    plat_ip_reg,
)
from files.factory import ManagerFactory
from gcloud.conf import settings
from gcloud.utils.handlers import handle_api_error
from gcloud.core.models import EnvironmentVariables

__group_name__ = _("作业平台(JOB)")

get_client_by_user = settings.ESB_GET_CLIENT_BY_USER

job_handle_api_error = partial(handle_api_error, __group_name__)


class JobPushLocalFilesService(JobService):
    __need_schedule__ = True

    reload_outputs = False

    def inputs_format(self):
        return []

    def outputs_format(self):
        return []

    def execute(self, data, parent_data):
        executor = parent_data.inputs.executor
        biz_cc_id = data.inputs.biz_cc_id
        local_files = data.inputs.job_local_files
        target_ip_list = data.inputs.job_target_ip_list
        target_account = data.inputs.job_target_account
        target_path = data.inputs.job_target_path
        across_biz = data.get_one_of_inputs("job_across_biz", False)

        file_manager_type = EnvironmentVariables.objects.get_var("BKAPP_FILE_MANAGER_TYPE")
        if not file_manager_type:
            data.outputs.ex_data = "File Manager configuration error, contact administrator please."
            return False

        try:
            file_manager = ManagerFactory.get_manager(manager_type=file_manager_type)
        except Exception as e:
            err_msg = "can not get file manager for type: {}\n err: {}"
            self.logger.error(err_msg.format(file_manager_type, traceback.format_exc()))
            data.outputs.ex_data = err_msg.format(file_manager_type, e)
            return False

        client = get_client_by_user(executor)

        # 跨业务
        if across_biz:
            ip_info = {"ip_result": []}
            for match in plat_ip_reg.finditer(target_ip_list):
                if not match:
                    continue
                ip_str = match.group()
                cloud_id, inner_ip = ip_str.split(":")
                ip_info["ip_result"].append({"InnerIP": inner_ip, "Source": cloud_id})
        else:
            ip_info = cc_get_ips_info_by_str(executor, biz_cc_id, target_ip_list)

        ip_list = [{"ip": _ip["InnerIP"], "bk_cloud_id": _ip["Source"]} for _ip in ip_info["ip_result"]]

        if not ip_list:
            data.outputs.ex_data = _("目标ip为空，请确认是否为当前业务IP。如需跨业务上传，请选择'允许跨业务'选项")
            return False

        # 这里自动过滤掉上传失败的文件
        file_tags = [_file["response"]["tag"] for _file in local_files if _file["response"]["result"] is True]

        push_result = file_manager.push_files_to_ips(
            esb_client=client,
            bk_biz_id=biz_cc_id,
            file_tags=file_tags,
            target_path=target_path,
            ips=ip_list,
            account=target_account,
            callback_url=get_node_callback_url(self.id, getattr(self, "version", "")),
        )

        if not push_result["result"]:
            err_message = job_handle_api_error(push_result["job_api"], push_result["kwargs"], push_result["response"])
            self.logger.error(err_message)
            data.outputs.ex_data = err_message
            return False

        job_instance_id = push_result["data"]["job_id"]
        data.outputs.job_inst_id = job_instance_id
        data.outputs.job_inst_url = get_job_instance_url(biz_cc_id, job_instance_id)
        return True


class JobPushLocalFilesComponent(Component):
    name = _("分发本地文件")
    code = "job_push_local_files"
    bound_service = JobPushLocalFilesService
    form = "%scomponents/atoms/job/job_push_local_files/v1_0_0.js" % settings.STATIC_URL
    version = "1.0.0"
