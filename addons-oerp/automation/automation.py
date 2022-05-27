# -*- coding: utf-8 -*-
#############################################################################
#
#    Copyright (c) 2007 Martin Reisenhofer <martin.reisenhofer@funkring.net>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import requests
import urlparse
import uuid
import json
import time

import logging


from openerp import models, fields, api, _
from openerp.addons.at_base import util
from openerp import SUPERUSER_ID
from openerp.exceptions import Warning


_logger = logging.getLogger(__name__)


def _list_all_models(self):
    self._cr.execute("SELECT model, name FROM ir_model ORDER BY name")
    return self._cr.fetchall()


class TaskLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.name = name
        self._status = None
        self._progress = 0
        self._loopInc = 0.0
        self._loopProgress = 0.0
        self.errors = 0
        self.warnings = 0

    def log(
        self, message, pri="i", obj=None, ref=None, progress=None, code=None, data=None
    ):
        if pri == "i":
            self.logger.info(message)
        elif pri == "e":
            self.errors += 1
            self.logger.error(message)
        elif pri == "w":
            self.warnings += 1
            self.logger.warning(message)
        elif pri == "d":
            self.logger.debug(message)
        elif pri == "x":
            self.logger.fatal(message)
        elif pri == "a":
            self.logger.critical(message)

    def loge(self, message, pri="e", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logw(self, message, pri="w", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logd(self, message, pri="d", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logn(self, message, pri="n", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def loga(self, message, pri="a", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logx(self, message, pri="x", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def initLoop(self, loopCount, status=None):
        self._loopProgress = 0.0
        if not loopCount:
            self._loopProgress = 100.0
            self._loopInc = 0.0
        else:
            self._loopInc = 100.0 / loopCount
            self._loopProgress = 0.0
        self.progress(status, self._loopProgress)

    def nextLoop(self, status=None, step=1):
        self._loopProgress += self._loopInc * step
        self.progress(status, self._loopProgress)

    def progress(self, status, progress):
        progress = min(round(progress), 100)
        if not status:
            status = "Progress"
        if self._status != status or self._progress != progress:
            self._status = status
            self._progress = progress
            self.log("%s: %s" % (self._status, self._progress))

    def stage(self, subject, total=None):
        self.log("= %s" % subject)

    def substage(self, subject, total=None):
        self.log("== %s" % subject)

    def done(self):
        self.progress("Done", 100.0)

    def close(self):
        pass


class TaskStatus(object):
    def __init__(self, task, total=1, local=False, logger=None, logging=False):
        self.task = task

        self.logger = logger
        if not self.logger and logging:
            self.logger = _logger

        self.local = local

        if self.local:
            self.stage_obj = self.task.env["automation.task.stage"]
            self.log_obj = self.task.env["automation.task.log"]
            self.log_obj.search([("task_id", "=", self.task.id)]).unlink()
            self.stage_obj.search([("task_id", "=", self.task.id)]).unlink()

            self.log_path = ""
            self.stage_path = ""
            self.progress_path = ""

        else:
            secret = self.task.env["automation.task.secret"].search(
                [("task_id", "=", task.id)]
            )
            if not secret:
                raise Warning(
                    _("No scecret for task %s [%s] was generated")
                    % (self.task, self.task.id)
                )
            else:
                secret = secret[0].secret

            baseurl = self.task.env["ir.config_parameter"].get_param("web.base.url")
            if not baseurl:
                raise Warning(_("Cannot determine base url"))

            # init path
            self.log_path = urlparse.urljoin(
                baseurl, "http/log/%s/%s" % (task.id, secret)
            )
            self.stage_path = urlparse.urljoin(
                baseurl, "http/stage/%s/%s" % (task.id, secret)
            )
            self.progress_path = urlparse.urljoin(
                baseurl, "http/progress/%s/%s" % (task.id, secret)
            )

        # setup root stage
        self.root_stage_id = self._create_stage({"name": task.name, "total": total})
        self.parent_stage_id = self.root_stage_id
        self.stage_id = self.root_stage_id

        self.parent_stage_name = ""
        self.stage_name = task.name

        # first log
        self.log(_("Started"))

        # stack
        self.stage_stack = []
        self.last_status = None
        self.errors = 0
        self.warnings = 0

        # loop
        self._loopInc = 0.0
        self._loopProgress = 0.0

    def _post_progress(self, data):
        if self.local:
            self.stage_obj.browse(data["stage_id"]).write(
                {
                    "task_id": self.task.id,
                    "status": data["status"],
                    "progress": data["progress"],
                }
            )
        else:
            res = requests.post(self.progress_path, data)
            res.raise_for_status()

    def _post_stage(self, data):
        if self.logger:
            self.logger.info("= Stage %s" % data["name"])
        if self.local:
            data["task_id"] = self.task.id
            return self.stage_obj.create(data).id
        else:
            res = requests.post(self.stage_path, data=data)
            res.raise_for_status()
            return int(res.text)

    def _post_log(self, data):
        # check for local logging
        if self.local:

            ref = data.get("ref")
            if ref:
                ref_parts = ref.split(",")
                ref_obj = ref_parts[0]
                ref_id = long(ref_parts[1])
                name = self.log_obj.env[ref_obj].browse(ref_id).name_get()[0]
                data["message"] = "%s (%s,'%s')" % (data["message"], name[0], name[1])

            # add progress
            if "progress" in data:
                progress = data.pop("progress", 0.0)
                self.task.env["automation.task.stage"].browse(self.stage_id).write(
                    {"progress": progress}
                )

            data["task_id"] = self.task.id
            self.log_obj.create(data)

        # otherwise forward log to server
        else:
            res = requests.post(self.log_path, data=data)
            res.raise_for_status()

        # log message
        if self.logger:
            pri = data["pri"]
            message = data["message"]
            if pri == "i":
                self.logger.info(message)
            elif pri == "e":
                self.errors += 1
                self.logger.error(message)
            elif pri == "w":
                self.warnings += 1
                self.logger.warning(message)
            elif pri == "d":
                self.logger.debug(message)
            elif pri == "x":
                self.logger.fatal(message)
            elif pri == "a":
                self.logger.critical(message)

    def log(
        self, message, pri="i", obj=None, ref=None, progress=None, code=None, data=None
    ):
        if pri == "e":
            self.errors += 1
        elif pri == "w":
            self.warnings += 1

        if not data is None and not isinstance(data, basestring):
            data = json.dumps(data)

        values = {
            "stage_id": self.stage_id,
            "pri": pri,
            "message": message,
            "code": code,
            "data": data,
        }
        if progress:
            values["progress"] = progress
        if obj:
            ref = "%s,%s" % (obj._name, obj.id)
        if ref:
            values["ref"] = ref

        self._post_log(values)

    def loge(self, message, pri="e", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logw(self, message, pri="w", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logd(self, message, pri="d", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logn(self, message, pri="n", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def loga(self, message, pri="a", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def logx(self, message, pri="x", **kwargs):
        self.log(message, pri=pri, **kwargs)

    def initLoop(self, loopCount, status=None):
        self._loopProgress = 0.0
        if not loopCount:
            self._loopProgress = 100.0
            self._loopInc = 0.0
        else:
            self._loopInc = 100.0 / loopCount
            self._loopProgress = 0.0
        self.progress(status, self._loopProgress)

    def nextLoop(self, status=None, step=1):
        self._loopProgress += self._loopInc * step
        self.progress(status, self._loopProgress)

    def progress(self, status, progress):
        values = {
            "stage_id": self.stage_id,
            "status": status,
            "progress": min(round(progress), 100),
        }
        if self.last_status is None or self.last_status != values:
            self.last_status = values
            self._post_progress(values)

    def _create_stage(self, values):
        return self._post_stage(values)

    def stage(self, subject, total=None):
        values = {"parent_id": self.parent_stage_id, "name": subject}
        if total:
            values["total"] = total
        self.stage_stack.append((self.parent_stage_id, self.stage_id))
        self.stage_id = self._create_stage(values)

    def substage(self, subject, total=None):
        values = {"parent_id": self.stage_id, "name": subject}
        if total:
            values["total"] = total
        self.stage_stack.append((self.parent_stage_id, self.stage_id))
        self.parent_stage_id = self.stage_id
        self.stage_id = self._create_stage(values)

    def done(self):
        self.progress(_("Done"), 100.0)
        if self.stage_stack:
            self.parent_stage_id, self.stage_id = self.stage_stack.pop()

    def close(self):
        self._post_progress(
            {"stage_id": self.root_stage_id, "status": _("Done"), "progress": 100.0}
        )


class automation_task(models.Model):
    _name = "automation.task"
    _description = "Automation Task"
    _order = "id asc"

    name = fields.Char(
        "Name", required=True, readonly=True, states={"draft": [("readonly", False)]}
    )

    state_change = fields.Datetime(
        "State Change",
        default=lambda self: util.currentDateTime(),
        required=True,
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("run", "Running"),
            ("cancel", "Canceled"),
            ("failed", "Failed"),
            ("done", "Done"),
        ],
        required=True,
        index=True,
        readonly=True,
        default="draft",
        copy=False,
    )

    progress = fields.Float("Progress", readonly=True, compute="_progress")
    error = fields.Text("Error", readonly=True, copy=False)
    owner_id = fields.Many2one(
        "res.users",
        "Owner",
        required=True,
        default=lambda self: self._uid,
        index=True,
        readonly=True,
    )
    res_model = fields.Char("Resource Model", index=True, readonly=True)
    res_id = fields.Integer("Resource ID", index=True, readonly=True)
    res_ref = fields.Reference(
        _list_all_models, string="Resource", compute="_res_ref", readonly=True
    )
    cron_id = fields.Many2one(
        "ir.cron",
        "Scheduled Job",
        index=True,
        ondelete="set null",
        copy=False,
        readonly=True,
    )
    total_logs = fields.Integer("Total Logs", compute="_total_logs")
    total_stages = fields.Integer("Total Stages", compute="_total_stages")
    total_warnings = fields.Integer("Total Warnings", compute="_total_warnings")

    task_id = fields.Many2one("automation.task", "Task", compute="_task_id", store=False)
  
    start_after_task_id = fields.Many2one(
        "automation.task",
        "Start after task",
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Start *this* task after the specified task, was set to null after queued."
    )    

    start_after = fields.Datetime(
        "Start After", help="Start *this* task after the specified date/time, was set to null after queued."
    )

    parent_id = fields.Many2one(
        "automation.task",
        "Parent",
        readonly=True,
        index=True,
        ondelete="set null",
        help="The parent task, after *this* task was started"
    )

    post_task_ids = fields.One2many(
        "automation.task",
        "start_after_task_id",
        "Post Tasks",
        help="Tasks which are started after this task.",
        readonly=True    
    )

    child_task_ids = fields.One2many(
        "automation.task",
        "parent_id",
        "Child Tasks",
        help="Tasks which already started after this task.",
        readonly=True    
    )

   
    @api.multi
    def _task_id(self):
        for task in self:
            self.task_id = task.id

    @api.multi
    def _progress(self):
        res = dict.fromkeys(self.ids, 0.0)
        cr = self._cr

        # search stages
        cr.execute(
            "SELECT id FROM automation_task_stage WHERE task_id IN %s AND parent_id IS NULL",
            (tuple(self.ids),),
        )

        # get progress
        stage_ids = [r[0] for r in cr.fetchall()]
        for stage in self.env["automation.task.stage"].browse(stage_ids):
            res[stage.task_id.id] = stage.complete_progress

        # assign
        for r in self:
            r.progress = res[r.id]

    @api.one
    def _res_ref(self):
        if self.res_model and self.res_id:
            res = self.env[self.res_model].search_count([("id", "=", self.res_id)])
            if res:
                self.res_ref = "%s,%s" % (self.res_model, self.res_id)
            else:
                self.res_ref = None
        else:
            self.res_ref = None

    @api.multi
    def _total_logs(self):
        res = dict.fromkeys(self.ids, 0)
        cr = self._cr
        cr.execute(
            "SELECT task_id, COUNT(*) FROM automation_task_log WHERE task_id IN %s GROUP BY 1",
            (tuple(self.ids),),
        )
        for task_id, log_count in cr.fetchall():
            res[task_id] = log_count
        for r in self:
            r.total_logs = res[r.id]

    @api.multi
    def _total_warnings(self):
        res = dict.fromkeys(self.ids, 0)
        cr = self._cr
        cr.execute(
            "SELECT task_id, COUNT(*) FROM automation_task_log WHERE pri IN ('a','e','w','x') AND task_id IN %s GROUP BY 1",
            (tuple(self.ids),),
        )
        for task_id, log_count in cr.fetchall():
            res[task_id] = log_count
        for r in self:
            r.total_warnings = res[r.id]

    @api.multi
    def _total_stages(self):
        res = dict.fromkeys(self.ids, 0)
        cr = self._cr
        cr.execute(
            "SELECT task_id, COUNT(*) FROM automation_task_stage WHERE task_id IN %s GROUP BY 1",
            (tuple(self.ids),),
        )
        for task_id, stage_count in cr.fetchall():
            res[task_id] = stage_count
        for r in self:
            r.total_stages = res[r.id]

    @api.one
    def _run(self, taskc):
        """" Test Task """
        for stage in range(1, 10):
            taskc.stage("Stage %s" % stage)

            for proc in range(1, 100, 10):
                taskc.log("Processing %s" % stage)
                taskc.progress("Processing %s" % stage, proc)
                time.sleep(1)

            taskc.done()

    def _stage_count(self):
        self.ensure_one()
        return 10

    def _task_get_list(self):
        self.ensure_one()

        task_id = self.id
        _cr = self._cr
        _cr.execute("""WITH RECURSIVE task(id) AS ( 
                SELECT
                    id
                FROM automation_task t
                WHERE 
                    t.id = %s
                UNION
                    SELECT
                        st.id
                    FROM automation_task st
                    INNER JOIN task pt ON st.start_after_task_id = pt.id
            )             
            SELECT id FROM task          
            """
         , (task_id, ))

        task_ids = [r[0] for r in _cr.fetchall()]
        return self.browse(task_ids)

    def _task_get_after_tasks(self):
        return self.search([("start_after_task_id","=",self.id)])

    def _task_add_after_last(self, task):
        """ Add task after this, if it is already
            queued it will be not queued twice """
        self.ensure_one()
        if task:
            tasklist = self._task_get_list()
            if not task in tasklist:
                task.write({
                    "start_after_task_id": tasklist[-1].id
                })           

    def _task_insert_after(self, task):
        """ Insert task after this """
        self.ensure_one()
        if task:
            task.start_after_task_id = task
            self.search([("start_after_task_id", "=", task.id)]).write({
                "start_after_task_id": self.id
            })     

    def _check_execution_rights(self):
        # check rights
        if self.owner_id.id != self._uid and not self.user_has_groups(
            "automation.group_automation_manager,base.group_system"
        ):
            raise Warning(
                _(
                    "Not allowed to start task. You be the owner or an automation manager"
                )
            )

    def _task_enqueue(self):
        """ queue task """ 
        self.ensure_one()
               
        # add cron entry
        cron = self.cron_id
        if not cron:
            cron = (self.env["ir.cron"].sudo().create(
                self._get_cron_values()))
        else:
            cron.write(self._get_cron_values())

        # set stages inactive
        self._cr.execute(
            "DELETE FROM automation_task_stage WHERE task_id=%s",
            (self.id, ),
        )

        # create secret
        secret_obj = self.env["automation.task.secret"]
        if not secret_obj.search([("task_id", "=", self.id)]):
            secret_obj.create({"task_id": self.id})

        # set queued
        self.write({
            "state": "queued",
            "parent_id": self.start_after_task_id.id,
            "start_after_task_id": None,
            "start_after": None,
            "cron_id": cron.id
        })

    @api.multi
    def action_cancel(self):
        for task in self:
            # check rights
            task._check_execution_rights()
            if task.state == "queued":
                task.state = "cancel"
        return True

    @api.multi
    def action_refresh(self):
        return True

    @api.multi
    def action_reset(self):
        return True

    def action_queue(self):
        for task in self:
            # check rights
            task._check_execution_rights()
            if task.state in ("draft", "cancel", "failed", "done"):
                # sudo task
                task.sudo()._task_enqueue()            
        return True

    def _get_cron_values(self):
        self.ensure_one()

        # start after is set
        # use start_after date instead of next call
        nextcall = util.currentDateTime()
        if nextcall < self.start_after:
            nextcall = self.start_after

        # new cron entry
        return {
            "name": "Task: %s" % self.name,
            "user_id": SUPERUSER_ID,
            "interval_type": "minutes",
            "interval_number": 1,
            "nextcall": nextcall,
            "numbercall": 1,
            "model": self._name,
            "function": "_process_task",
            "args": "(%s,)" % self.id,
            "active": True,
            "priority": 1000 + self.id,
            "task_id": self.id,
        }

    @api.model
    def _cleanup_tasks(self):
        # clean up cron tasks
        self._cr.execute("DELETE FROM ir_cron WHERE task_id IS NOT NULL AND NOT active")
        return True

    @api.model
    def _process_task(self, task_id):
        task = self.browse(task_id)
        if task and task.state == "queued":
            try:
                # get options
                if task.res_model and task.res_id:
                    model_obj = self.env[task.res_model]
                    resource = model_obj.browse(task.res_id)
                else:
                    resource = task

                # options

                options = {"stages": 1, "resource": resource}

                # get custom options

                if hasattr(resource, "_run_options"):
                    res_options = getattr(resource, "_run_options")
                    if callable(res_options):
                        res_options = resource._run_options()
                    options.update(res_options)

                stage_count = options["stages"]

                # check if it is a singleton task
                # if already another task run, requeue
                # don't process this task
                if options.get("singleton"):
                    # cleanup
                    self._cr.execute(
                        "DELETE FROM ir_cron WHERE task_id=%s AND id!=%s AND NOT active",
                        (task.id, task.cron_id.id),
                    )
                    # check concurrent
                    self._cr.execute(
                        "SELECT MIN(id) FROM automation_task WHERE res_model=%s AND state IN ('queued','run')",
                        (resource._model._name,),
                    )
                    active_task_id = self._cr.fetchone()[0]
                    if active_task_id and active_task_id < task_id:
                        # requeue
                        task.cron_id = self.env["ir.cron"].create(
                            task._get_cron_values()
                        )
                        return True

                # change task state
                # and commit
                task.write(
                    {
                        "state_change": util.currentDateTime(),
                        "state": "run",
                        "error": None,
                    }
                )
                # commit after start
                self._cr.commit()
                
                # run task
                taskc = TaskStatus(task, stage_count)
                resource._run(taskc)
                
                # check fail on errors
                if options.get("fail_on_errors"):
                    if taskc.errors:
                        raise Warning("Task finished with errors")

                # close
                taskc.close()

                # update status
                task.write(
                    {
                        "state_change": util.currentDateTime(),
                        "state": "done",
                        "error": None,                        
                    }
                )

                # commit after finish
                self._cr.commit()
                self.refresh()

                # queue task after                 
                for post_task in task.post_task_ids:
                    post_task.action_queue()

            except Exception as e:
                # rollback on error
                self._cr.rollback()
                _logger.exception("Task execution failed")

                error = str(e)
                if not error and hasattr(e, "message"):
                    error = e.message

                if not error:
                    error = "Unexpected error, see logs"

                # write error
                task.write(
                    {
                        "state_change": util.currentDateTime(),
                        "state": "failed",
                        "error": error,
                    }
                )
                self._cr.commit()

        return True


class automation_task_stage(models.Model):
    _name = "automation.task.stage"
    _description = "Task Stage"
    _order = "id asc"
    _rec_name = "complete_name"

    complete_name = fields.Char("Name", compute="_complete_name")
    complete_progress = fields.Float(
        "Progess %", readonly=True, compute="_complete_progress"
    )

    name = fields.Char("Name", readonly=True, required=True)
    progress = fields.Float("Progress %", readonly=True)
    status = fields.Char("Status")

    task_id = fields.Many2one(
        "automation.task",
        "Task",
        readonly=True,
        index=True,
        required=True,
        ondelete="cascade",
    )
    parent_id = fields.Many2one(
        "automation.task.stage", "Parent Stage", readonly=True, index=True
    )
    total = fields.Integer("Total", readonly=True)

    child_ids = fields.One2many(
        "automation.task.stage", "parent_id", string="Substages", copy=False
    )

    @api.one
    def _complete_name(self):
        name = []
        stage = self
        while stage:
            name.append(stage.name)
            stage = stage.parent_id
        self.complete_name = " / ".join(reversed(name))

    @api.model
    def _calc_progress(self, stage):
        progress = stage.progress
        if progress >= 100.0:
            return progress

        childs = stage.child_ids
        total = max(stage.total, len(childs)) or 1

        for child in childs:
            progress += self._calc_progress(child) / total

        return min(round(progress), 100.0)

    @api.one
    def _complete_progress(self):
        self.complete_progress = self._calc_progress(self)


class automation_task_log(models.Model):
    _name = "automation.task.log"
    _description = "Task Log"
    _order = "id asc"
    _rec_name = "create_date"

    task_id = fields.Many2one(
        "automation.task",
        "Task",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    stage_id = fields.Many2one(
        "automation.task.stage",
        "Stage",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
    )

    pri = fields.Selection(
        [
            ("x", "Emergency"),
            ("a", "Alert"),
            ("e", "Error"),
            ("w", "Warning"),
            ("n", "Notice"),
            ("i", "Info"),
            ("d", "Debug"),
        ],
        string="Priority",
        default="i",
        index=True,
        required=True,
        readonly=True,
    )

    message = fields.Text("Message", readonly=True)
    ref = fields.Reference(
        _list_all_models, string="Reference", readonly=True, index=True
    )
    code = fields.Char("Code", index=True)
    data = fields.Json("Data")


class task_secret(models.Model):
    _name = "automation.task.secret"
    _rec_name = "task_id"

    task_id = fields.Many2one(
        "automation.task", "Task", requird=True, ondelete="cascade", index=True
    )
    secret = fields.Char(
        "Secret", required=True, default=lambda self: uuid.uuid4().hex, index=True
    )
