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

from openerp.osv import fields, osv
from openerp.exceptions import Warning

from openerp.addons.at_base import util
from openerp.addons.at_base import helper
from openerp.addons.at_base import format

from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp import SUPERUSER_ID


class sale_shop(osv.osv):
    _inherit = "sale.shop"
    _columns = {
        "autocreate_order_parent_id": fields.many2one(
            "account.analytic.account",
            "Analytic account default parent",
            domain=[("type", "=", "view")],
        ),
        "autocreate_order_analytic_account": fields.boolean(
            "Analytic Account per Order"
        ),
        "project_template_id": fields.many2one("project.project", "Project template"),
    }


class sale_order(osv.osv):
    def _project_name_get(self, cr, uid, order_values):
        order_name = order_values.get("name", "")
        client_order_ref = order_values.get("client_order_ref")
        if client_order_ref:
            return "%s / %s" % (order_name, client_order_ref)
        return order_name

    def onchange_shop_id(self, cr, uid, ids, shop_id, state, project_id, context=None):
        res = super(sale_order, self).onchange_shop_id(
            cr, uid, ids, shop_id, state, project_id, context=context
        )
        if shop_id:
            shop = self.pool["sale.shop"].browse(cr, uid, shop_id)
            value = res["value"]
            if shop.autocreate_order_analytic_account:
                account_id = value.get("project_id") or project_id
                if account_id:
                    if not ids:
                        value["project_id"] = None
                    else:
                        value["project_id"] = self.pool[
                            "account.analytic.account"
                        ].search_id(
                            cr,
                            SUPERUSER_ID,
                            [("order_id", "in", ids), ("id", "=", account_id)],
                        )
        return res

    #    TODO: For this Workflow has to be extended, that means
    #          after finishing the shipping a manual invoice have to be started
    #          of only service products and one product with auto_create_task are
    #          contained
    #
    #     def test_no_product(self, cr, uid, order, context):
    #         for line in order.order_line:
    #             if line.state == "cancel":
    #                 continue
    #             product = line.product_id
    #             if product and (product.type != 'service' or product.auto_create_task):
    #                 return False
    #         return True

    def _correct_analytic_values(self, cr, uid, order_id, vals, context=None):
        """ Sync analytic account and sale order

            :returns: analytic account id if a new one is created otherwise False is returned
        """

        def getValue(inDict, inKey, inOverride=None):
            if inDict:
                # get value
                if inOverride and inKey in inOverride:
                    res = inOverride[inKey]
                else:
                    res = inDict.get(inKey, None)

                # check if it is a link
                if isinstance(res, tuple) and len(res) == 2:
                    return res[0]

                return res

            # return none if empty
            return None

        analytic_id = None
        order_values = {}

        order_read = vals
        if order_id:
            order_read = self.read(
                cr,
                uid,
                order_id,
                [
                    "project_id",
                    "partner_id",
                    "pricelist_id",
                    "name",
                    "shop_id",
                    "client_order_ref",
                ],
                context,
            )
        else:
            if not vals.get("name"):
                vals["name"] = self.default_get(cr, uid, ["name"], context)["name"]

        analytic_id = order_values["project_id"] = getValue(
            order_read, "project_id", vals
        )
        shop_id = order_values["shop_id"] = getValue(
            order_read, "shop_id", vals
        ) or context.get("shop", None)
        order_values["partner_id"] = getValue(order_read, "partner_id", vals)
        order_values["pricelist_id"] = getValue(order_read, "pricelist_id", vals)
        order_values["client_order_ref"] = getValue(
            order_read, "client_order_ref", vals
        )
        order_values["name"] = getValue(order_read, "name", vals)

        if shop_id:
            shop = self.pool.get("sale.shop").browse(cr, uid, shop_id, context=context)
            if shop.autocreate_order_analytic_account:
                # init vars
                analytic_obj = self.pool.get("account.analytic.account")
                project_context = context.copy()
                project_vals = {}
                project_name = self._project_name_get(cr, uid, order_values)
                partner_id = order_values["partner_id"]
                pricelist_id = order_values["pricelist_id"]

                # init all and determine parent project
                shop_analytic_parent_id = shop.autocreate_order_parent_id.id
                parent_analytic = None

                # get parent project
                parent_analytic_id = context.get("parent_project_id", None)
                if parent_analytic_id:
                    parent_analytic = analytic_obj.browse(
                        cr, uid, parent_analytic_id, context=context
                    )
                elif analytic_id:
                    analytic = analytic_obj.browse(
                        cr, uid, analytic_id, context=context
                    )
                    parent_analytic = analytic.parent_id

                # check if parent is valid
                if parent_analytic:
                    # reset project parent if it has not an order id
                    if not parent_analytic.order_id:
                        parent_analytic = None
                    else:
                        # reset parent_analytic if parent_analytic shop is not the same
                        # as the shop now
                        shop_obj = self.pool.get("sale.shop")
                        parent_shop_id = shop_obj.search_id(
                            cr,
                            uid,
                            [("autocreate_order_parent_id", "=", parent_analytic.id)],
                        )
                        if parent_shop_id and parent_shop_id != shop_id:
                            parent_shop_id = None

                # check for partner project
                if partner_id:
                    partner = self.pool.get("res.partner").browse(cr, uid, partner_id)
                    partner_account = partner.property_partner_analytic_account
                    if partner_account:
                        parent_analytic = partner_account

                # set values, these values are only written
                # if project exists or a new one is created
                project_vals["parent_id"] = (
                    parent_analytic and parent_analytic.id
                ) or shop_analytic_parent_id
                project_vals["code"] = order_values.get("name")
                project_vals["order_id"] = order_id
                project_vals["name"] = project_name
                project_context["default_name"] = project_name
                if partner_id:
                    project_vals["partner_id"] = partner_id
                if pricelist_id:
                    project_vals["pricelist_id"] = pricelist_id

                # check if there is already an project to link
                proj_obj = self.pool.get("project.project")
                proj_id = None

                # search project to order
                if order_id:
                    # if analytic id exist, search project with account
                    if analytic_id:
                        proj_id = proj_obj.search_id(
                            cr,
                            uid,
                            [
                                ("analytic_account_id.order_id", "=", order_id),
                                ("analytic_account_id", "=", analytic_id),
                            ],
                        )
                    # otherwise search without account
                    else:
                        proj_id = proj_obj.search_id(
                            cr, uid, [("analytic_account_id.order_id", "=", order_id)]
                        )
                        analytic_id = getValue(
                            proj_obj.read(
                                cr, uid, proj_id, ["analytic_account_id"], context
                            ),
                            "analytic_account_id",
                        )

                # template
                template_id = (
                    shop.project_template_id and shop.project_template_id.id or None
                )

                # create new or recreate from template if template has changed, only if analytic account created for this order
                if not analytic_id:
                    # create new or copy from template
                    project_vals["user_id"] = uid
                    project_vals["state"] = "draft"
                    if shop.project_template_id:
                        proj_id = proj_obj.copy(
                            cr, uid, template_id, project_vals, project_context
                        )
                    else:
                        proj_id = proj_obj.create(
                            cr, uid, project_vals, project_context
                        )

                    # get analytic account
                    analytic_id = getValue(
                        proj_obj.read(
                            cr, uid, proj_id, ["analytic_account_id"], context
                        ),
                        "analytic_account_id",
                    )
                    vals["project_id"] = analytic_id
                    return analytic_id

                # update current, if there exist a project to order
                elif proj_id:

                    # get order
                    order = None
                    order_project_template_id = None
                    if order_id:
                        order = self.browse(cr, uid, order_id, context=context)
                        order_project_template_id = (
                            order.shop_id.project_template_id
                            and order.shop_id.project_template_id.id
                        )

                    # get project
                    proj = proj_obj.browse(cr, uid, proj_id, context=context)

                    # proj update should be done?
                    proj_update = (
                        order
                        and order.state == "draft"
                        and proj_id
                        and template_id
                        and order_project_template_id != template_id
                    )

                    # check if data from project vals are to update
                    if proj_update:
                        project_tmp_vals = proj_obj.copy_data(
                            cr, uid, template_id, context=project_context
                        )
                        project_tmp_vals.update(project_vals)
                        project_vals = project_tmp_vals

                    proj_obj.write(cr, uid, [proj_id], project_vals, project_context)
                    vals["project_id"] = analytic_id

                    # update all tasks
        #                     if proj_update:
        #                         proj = proj_obj.browse(cr, uid, proj_id, context=context)
        #                         task_obj = self.pool["project.task"]
        #                         cr.execute("SELECT t.id FROM project_task t WHERE t.project_id = %s", (proj_id,))
        #                         task_ids = [r[0] for r in cr.fetchall()]
        #                         if task_ids:
        #                             for task_id in task_ids:
        #                                 task_onchange_res = task_obj.onchange_project(cr, SUPERUSER_ID, task_id, proj_id, context=context)
        #                                 task_values = task_onchange_res and task_onchange_res["value"] or {}
        #                                 task_values["project_id"] = proj_id
        #                                 task_obj.write(cr, SUPERUSER_ID, [task_id], task_values, context=context)

        return False

    def _is_correct_analytic_field(self, cr, uid, vals, context=None):
        return (
            vals.has_key("name")
            or vals.has_key("partner_id")
            or vals.has_key("pricelist_id")
            or vals.has_key("shop_id")
            or vals.has_key("client_order_ref")
        )

    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}
        if self._is_correct_analytic_field(cr, uid, vals, context):
            ids = util.idList(ids)
            for oid in ids:
                corrected_vals = vals.copy()
                self._correct_analytic_values(cr, uid, oid, corrected_vals, context)
                super(sale_order, self).write(cr, uid, oid, corrected_vals, context)
            return True
        res = super(sale_order, self).write(cr, uid, ids, vals, context)
        return res

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        if vals.get("name", "/") == "/":
            vals["name"] = (
                self.pool.get("ir.sequence").get(cr, uid, "sale.order") or "/"
            )

        analytic_account_id = self._correct_analytic_values(
            cr, uid, None, vals, context
        )
        order_id = super(sale_order, self).create(cr, uid, vals, context)

        # check if a new analytic account is created
        # if it is, link it with order
        if order_id and analytic_account_id:
            analytic_account_obj = self.pool.get("account.analytic.account")
            analytic_account_obj.write(
                cr, uid, [analytic_account_id], {"order_id": order_id}, context=context
            )
        return order_id

    def _pre_calc(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        for obj in self.browse(cr, uid, ids, context):
            total = obj.margin
            total -= obj.timesheet_lines_amount
            res[obj.id] = total
        return res

    def _post_calc(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        for obj in self.browse(cr, SUPERUSER_ID, ids, context):
            res[obj.id] = obj.project_id and obj.project_id.balance or 0.0
        return res

    def _timesheet_lines(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        for oid in ids:
            res[oid] = []

        cr.execute(
            " SELECT o.id,tl.id FROM hr_analytic_timesheet AS tl "
            "   INNER JOIN account_analytic_line AS l ON l.id = tl.line_id "
            "   INNER JOIN account_analytic_account AS a ON a.id = l.account_id "
            "   INNER JOIN sale_order AS o ON o.project_id = a.id AND o.name = a.name "
            "   WHERE o.id IN %s"
            "   ORDER BY 1 ",
            (tuple(ids),),
        )

        for row in cr.fetchall():
            res[row[0]].append(row[1])
        return res

    def _timesheet_lines_amount(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids, 0.0)

        cr.execute(
            "SELECT o.id,SUM(l.amount) FROM hr_analytic_timesheet AS tl "
            "     INNER JOIN account_analytic_line AS l ON l.id = tl.line_id "
            "     INNER JOIN account_analytic_account AS a ON a.id = l.account_id "
            "     INNER JOIN sale_order AS o ON o.project_id = a.id AND o.name = a.name "
            "     WHERE o.id IN %s"
            "     GROUP BY 1 ",
            (tuple(ids),),
        )

        for row in cr.fetchall():
            res[row[0]] = row[1]
        return res

    def _contrib_margin_percent(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        for obj in self.browse(cr, uid, ids, context):
            margin = 0.0
            if obj.amount_untaxed:
                margin = 100.0 / obj.amount_untaxed * obj.margin
            res[obj.id] = margin
        return res

    def _linked_project_id(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        project_obj = self.pool["project.project"]
        project_ids = project_obj.search(cr, uid, [("order_id", "in", ids)])
        for project in project_obj.browse(cr, uid, project_ids, context=context):
            res[project.order_id.id] = project.id
        return res

    def copy_data(self, cr, uid, id, default=None, context=None):
        order = self.browse(cr, uid, id, context=context)

        # don't copy if auto create is enabled
        if (
            default is None or not "project_id" in default
        ) and order.shop_id.autocreate_order_analytic_account:
            if default is None:
                default = {}
            else:
                default = dict(default)
            default["project_id"] = None

        res = super(sale_order, self).copy_data(
            cr, uid, id, default=default, context=context
        )
        return res

    def action_button_confirm(self, cr, uid, ids, context=None):
        res = super(sale_order, self).action_button_confirm(
            cr, uid, ids, context=context
        )

        # open project after confirm
        project_obj = self.pool["project.project"]
        for order in self.browse(cr, uid, ids, context=context):
            project = order.order_project_id
            if project and project.state == "draft":
                project_obj.set_open(cr, uid, [project.id], context=context)

        return res

    def action_wait(self, cr, uid, ids, context=None):
        res = super(sale_order, self).action_wait(cr, uid, ids, context=context)

        # check if only contract
        for order in self.browse(cr, uid, ids, context=context):
            # count contract lines
            contract_count = 0
            for line in order.order_line:
                if line.is_contract:
                    contract_count += 1

            # signal all finished, if only contract
            if contract_count and contract_count == len(order.order_line):
                self.action_done(cr, uid, [order.id], context=context)

        return res

    _inherit = "sale.order"
    _columns = {
        "pre_calc": fields.function(
            _pre_calc,
            string="Pre Calculation (Netto)",
            type="float",
            digits_compute=dp.get_precision("Account"),
        ),
        "post_calc": fields.function(
            _post_calc,
            string="Post Calculation (Netto)",
            type="float",
            digits_compute=dp.get_precision("Account"),
        ),
        "margin_contrib_percent": fields.function(
            _contrib_margin_percent, string="Contribution Margin %", type="float"
        ),
        "timesheet_lines": fields.function(
            _timesheet_lines,
            string="Timesheet Lines",
            type="many2many",
            obj="hr.analytic.timesheet",
        ),
        "timesheet_lines_amount": fields.function(
            _timesheet_lines_amount,
            string="Timesheet Lines",
            type="float",
            digits_compute=dp.get_precision("Account"),
        ),
        "order_project_id": fields.function(
            _linked_project_id,
            relation="project.project",
            type="many2one",
            string="Project",
        ),
    }


class sale_order_line(osv.osv):
    def _prepare_order_line_invoice_line(
        self, cr, uid, line, account_id=False, context=None
    ):
        # if contract, no invoice
        if line.is_contract:
            return False

        res = super(sale_order_line, self)._prepare_order_line_invoice_line(
            cr, uid, line, account_id, context
        )

        product = line.product_id
        if product and product.type == "service" and product.billed_at_cost:
            task_obj = self.pool["project.task"]
            task_ids = task_obj.search(
                cr, SUPERUSER_ID, [("sale_line_id", "=", line.id)]
            )
            f = format.LangFormat(cr, uid, context=context)

            task_set = set()
            work_info = []
            effective_hours = 0.0

            # add task and childs
            def add_task(task):
                # check if task already processed
                if task.id in task_set:
                    return 0.0

                hours = 0.0

                # check work
                for work in task.work_ids:
                    if work.hours:
                        # round to quarter and add
                        work_minutes = round(work.hours * 60)
                        work_minutes_rest = work_minutes % 15
                        if work_minutes_rest:
                            work_minutes = work_minutes + (15 - work_minutes_rest)

                        task_hours = float(work_minutes) / 60.0
                        hours += task_hours

                        work_line = []

                        # append date
                        if work.date:
                            work_line.append(
                                f.formatLang(util.timeToDateStr(work.date), date=True)
                            )

                        # append time
                        work_line.append(
                            _("%s Hour(s)") % f.formatLang(task_hours, float_time=True)
                        )

                        # append name
                        if work.name:
                            work_line.append(work.name)

                        work_info.append(" - ".join(work_line))

                # add childs
                task_set.add(task.id)
                for child_task in task.child_ids:
                    hours += add_task(child_task)

                return hours

            # build task set
            for task in task_obj.browse(cr, SUPERUSER_ID, task_ids, context=context):
                effective_hours += add_task(task)

            # get quantity
            res["quantity"] = effective_hours
            # set new work info
            if work_info:
                res["name"] = "%s\n%s" % (res["name"], "\n".join(work_info))

        return res

    def _is_contract_product(self, cr, uid, product, context=None):
        if product and product.type == "service":
            return product.recurring_invoices
        return False

    def _is_task_product(self, cr, uid, product, context=None):
        if product and product.type == "service" and product.auto_create_task:
            return True
        return False

    def product_id_change_with_wh_price(
        self,
        cr,
        uid,
        ids,
        pricelist,
        product,
        qty=0,
        uom=False,
        qty_uos=0,
        uos=False,
        name="",
        partner_id=False,
        lang=False,
        update_tax=True,
        date_order=False,
        packaging=False,
        fiscal_position=False,
        flag=False,
        warehouse_id=False,
        route_id=False,
        price_unit=None,
        price_nocalc=False,
        context=None,
    ):

        res = super(sale_order_line, self).product_id_change_with_wh_price(
            cr,
            uid,
            ids,
            pricelist,
            product,
            qty=qty,
            uom=uom,
            qty_uos=qty_uos,
            uos=uos,
            name=name,
            partner_id=partner_id,
            lang=lang,
            update_tax=update_tax,
            date_order=date_order,
            packaging=packaging,
            fiscal_position=fiscal_position,
            flag=flag,
            warehouse_id=warehouse_id,
            route_id=route_id,
            price_unit=price_unit,
            price_nocalc=price_nocalc,
            context=context,
        )

        if product:
            product = self.pool["product.product"].browse(
                cr, uid, product, context=context
            )
            res["value"]["is_contract"] = self._is_contract_product(
                cr, uid, product, context=context
            )
            res["value"]["is_task"] = (
                self._is_task_product(cr, uid, product, context=context)
                or product.recurring_tmpl_id.recurring_task
            )

        return res

    def _is_contract(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids, False)
        for line in self.browse(cr, uid, ids, context):
            res[line.id] = self._is_contract_product(
                cr, uid, line.product_id, context=context
            )
        return res

    def _is_task(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids, False)
        for line in self.browse(cr, uid, ids, context):
            res[line.id] = (
                self._is_task_product(cr, uid, line.product_id, context=context)
                or line.product_id.recurring_tmpl_id.recurring_task
            )
        return res

    def _prepare_contract(self, cr, uid, line, context=None):
        product = line.product_id
        order = line.order_id
        partner = order.partner_invoice_id

        return {
            "name": line.contract_name,
            "partner_id": partner.id,
            "date_start": line.contract_start,
            "date": line.contract_end,
            "shop_id": order.shop_id.id,
            "src_order_id": order.id,
            "is_contract": True,
            "use_issues": True,
            "use_tasks": True,
            "use_timesheets": True,
        }

    def _convert_qty_company_hours(self, cr, uid, line, context=None):
        # take planned hours if defined
        product = line.product_id
        if product.planned_hours:
            return product.planned_hours

        # otherwise take it from sales
        # order line
        product_uom = self.pool.get("product.uom")
        company = line.order_id.company_id
        company_time_uom = company.project_time_mode_id
        if (
            line.product_uom.id != company_time_uom.id
            and line.product_uom.category_id.id == company_time_uom.category_id.id
        ):
            planned_hours = product_uom._compute_qty(
                cr,
                uid,
                line.product_uom.id,
                line.product_uom_qty,
                company_time_uom_id.id,
            )
        else:
            planned_hours = line.product_uom_qty
        return planned_hours

    def _prepare_task(self, cr, uid, line, context):
        order = line.order_id
        company = order.company_id
        product = line.product_id

        # get planned hours
        planned_hours = self._convert_qty_company_hours(cr, uid, line, context=context)

        # only one line name for short task names
        name = line.name.split("\n")[0]
        values = {
            "product_id": product.id,
            "name": name,
            "partner_id": line.order_id.partner_id.id,
            "sequence": line.sequence,
            "description": line.procurement_note,
            "planned_hours": planned_hours,
            "remaining_hours": planned_hours,
            "company_id": company.id,
        }
        if line.task_deadline:
            values["date_deadline"] = line.task_deadline
        return values

    def action_create_task(self, cr, uid, ids, context=None):
        task_obj = self.pool["project.task"]
        line_obj = self.pool["sale.order.line"]
        for line in self.browse(cr, uid, ids, context=context):
            order = line.order_id
            project = order.order_project_id
            if project:
                task_values = self._prepare_task(cr, uid, line, context)
                task_values["project_id"] = project.id
                if line.pre_task_id:
                    task_obj.write(
                        cr, uid, line.pre_task_id.id, task_values, context=context
                    )
                else:
                    task_id = task_obj.create(cr, uid, task_values, context=context)
                    line_obj.write(
                        cr, uid, line.id, {"pre_task_id": task_id}, context=context
                    )
        return True

    def _calc_contract(self, cr, uid, line, values, context=None):
        # set task start
        if values.get("recurring_task"):
            values["recurring_task_next"] = line.contract_start_task
        # set invoice start
        if values.get("recurring_invoices"):
            values["recurring_next_date"] = line.contract_start

        # if template is used, update
        # quantity and price of the same product
        product = line.product_id
        recurring_lines = values.get("recurring_invoice_line_ids")
        if recurring_lines:
            # search for same product
            for rec_line_update in recurring_lines:
                if (
                    len(rec_line_update) == 3
                    and rec_line_update[2].get("product_id") == product.id
                ):
                    rec_line_update[2].update(
                        {
                            "product_id": product.id,
                            "uom_id": line.product_uom.id,
                            "name": line.name,
                            "quantity": line.product_uom_qty,
                            "price_unit": line.price_unit,
                        }
                    )

    def action_create_contract(self, cr, uid, ids, context=None):
        account_obj = self.pool["account.analytic.account"]
        project_obj = self.pool["project.project"]

        for line in self.browse(cr, uid, ids, context=context):
            if line.is_contract:
                contract = None
                contract_id = False
                contract_ids = []
                if line.contract_id:
                    contract = line.contract_id
                    contract_id = line.contract_id.id
                    contract_ids = [contract_id]

                # check
                if not line.contract_name or not line.contract_start:
                    raise Warning(
                        _("No contract name or start date for %s") % line.name
                    )
                if line.contract_start < util.currentDate():
                    raise Warning(
                        _("Contract start date is before current date for %s")
                        % line.name
                    )
                if line.contract_end and line.contract_end < line.contract_start:
                    raise Warning(
                        _(
                            "Contract end date is before contract start date %s"
                            % line.name
                        )
                    )

                # check task specific
                if line.is_task:
                    if not line.contract_start_task:
                        raise Warning(_("No task start date for %s") % line.name)
                    if line.contract_start_task < util.currentDate():
                        raise Warning(
                            _("Task start date is before current date for %s")
                            % line.name
                        )

                # get values
                values = self._prepare_contract(cr, uid, line, context=context)
                if not values:
                    continue

                product = line.product_id
                recurring_tmpl = product.recurring_tmpl_id
                recurring_task = False

                # partner values
                helper.onChangeValuesPool(
                    cr,
                    uid,
                    account_obj,
                    values,
                    account_obj.on_change_partner_id(
                        cr,
                        uid,
                        contract_ids,
                        values.get("partner_id"),
                        name=values.get("name"),
                        context=context,
                    ),
                    context=context,
                )

                if recurring_tmpl:

                    # recurring values
                    values["template_id"] = recurring_tmpl.id
                    helper.onChangeValuesPool(
                        cr,
                        uid,
                        account_obj,
                        values,
                        account_obj.on_change_template(
                            cr,
                            uid,
                            contract_ids,
                            recurring_tmpl.id,
                            date_start=values.get("date_start"),
                            context=context,
                        ),
                        context=context,
                    )

                    # check if tonract already exist
                    if contract:
                        # recurring task update
                        if (
                            not values.get("recurring_task_ids")
                            and contract.recurring_task_ids
                        ):
                            recurring_task_update = []
                            for rec_task in contract.recurring_task_ids:
                                recurring_task_update.append(
                                    (
                                        1,
                                        rec_task.id,
                                        {
                                            "name": rec_task.name,
                                            "product_id": rec_task.product_id.id,
                                            "description": rec_task.description,
                                            "planned_hours": rec_task.planned_hours,
                                            "repeat": rec_task.repeat,
                                        },
                                    )
                                )
                            values["recurring_task_ids"] = recurring_task_update

                        # recurring invoice update
                        if (
                            not values.get("recurring_invoice_line_ids")
                            and contract.recurring_invoice_line_ids
                        ):
                            recurring_inv_update = []
                            for rec_inv in contract.recurring_invoice_line_ids:
                                recurring_inv_update.append(
                                    (
                                        1,
                                        rec_inv.id,
                                        {
                                            "product_id": rec_inv.product_id.id,
                                            "uom_id": rec_inv.uom_id.id,
                                            "name": rec_inv.name,
                                            "quantity": rec_inv.quantity,
                                            "price_unit": rec_inv.price_unit,
                                        },
                                    )
                                )
                                values[
                                    "recurring_invoice_line_ids"
                                ] = recurring_inv_update

                else:
                    # build on product

                    # check if task should created automatically
                    if product.auto_create_task:
                        values["recurring_task"] = True
                        values["recurring_interval"] = product.recurring_interval
                        values["recurring_task_rule"] = product.recurring_rule_type
                        values["recurring_task_next"] = line.contract_start_task

                        # check for existing task line
                        recurring_task_id = 0
                        recurring_found = 0
                        if contract:
                            for recurring_task in contract.recurring_task_ids:
                                recurring_task_id = recurring_task.id
                                recurring_found = 1

                        # prepare recurrent task template
                        values["recurring_task_ids"] = [
                            (
                                recurring_found,
                                recurring_task_id,
                                {
                                    "name": line.name.split("\n")[0],
                                    "product_id": line.product_id.id,
                                    "description": line.procurement_note,
                                    "planned_hours": product.planned_hours,
                                },
                            )
                        ]

                    # billed at cost task
                    if product.auto_create_task and product.billed_at_cost:
                        values["invoice_on_timesheets"] = True

                        # enable invoice on timesheets
                        helper.onChangeValuesPool(
                            cr,
                            uid,
                            account_obj,
                            values,
                            account_obj.onchange_invoice_on_timesheets(
                                cr, uid, contract_ids, True, context=context
                            ),
                            context=context,
                        )

                    else:
                        values["recurring_invoices"] = True
                        values["recurring_interval"] = product.recurring_interval
                        values["recurring_rule_type"] = product.recurring_rule_type

                        # check for existing line
                        recurring_invoice_line_id = 0
                        recurring_found = 0
                        if contract:
                            for (
                                recurring_invoice_line
                            ) in contract.recurring_invoice_line_ids:
                                recurring_invoice_line_id = recurring_invoice_line.id
                                recurring_found = 1

                        # only create invoice if it isn't a billed at cost task
                        values["recurring_invoice_line_ids"] = [
                            (
                                recurring_found,
                                recurring_invoice_line_id,
                                {
                                    "product_id": product.id,
                                    "uom_id": line.product_uom.id,
                                    "name": line.name,
                                    "quantity": line.product_uom_qty,
                                    "price_unit": line.price_unit,
                                },
                            )
                        ]

                # calc contract
                self._calc_contract(cr, uid, line, values, context)
                if contract_id:
                    # update
                    account_obj.write(cr, uid, contract_id, values, context=context)
                else:
                    # create
                    shop = line.order_id.shop_id
                    project_template = shop.project_template_id
                    if project_template:
                        project_id = project_obj.copy(
                            cr, uid, project_template.id, values, context=context
                        )
                        account_id = project_obj.browse(
                            cr, uid, project_id, context=context
                        ).analytic_account_id.id
                        self.write(
                            cr,
                            uid,
                            line.id,
                            {"contract_id": account_id},
                            context=context,
                        )
                    else:
                        account_id = account_obj.create(
                            cr, uid, values, context=context
                        )
                        self.write(
                            cr,
                            uid,
                            line.id,
                            {"contract_id": account_id},
                            context=context,
                        )

        return True

    def button_confirm(self, cr, uid, ids, context=None):
        res = super(sale_order_line, self).button_confirm(cr, uid, ids, context=context)
        self.action_create_contract(cr, uid, ids, context=context)
        return res

    _inherit = "sale.order.line"
    _columns = {
        "is_task": fields.function(_is_task, type="boolean", string="Is Task"),
        "is_contract": fields.function(
            _is_contract, type="boolean", string="Is Contract"
        ),
        "pre_task_id": fields.many2one(
            "project.task",
            "Created Task",
            help="Pre created Task before order was confirmed",
            readonly=True,
            copy=False,
        ),
        "task_deadline": fields.date(
            "Deadline",
            states={"draft": [("readonly", False)]},
            readonly=True,
            copy=False,
        ),
        "contract_start": fields.date(
            "Contract Start",
            states={"draft": [("readonly", False)]},
            readonly=True,
            copy=False,
        ),
        "contract_end": fields.date(
            "Contract End",
            states={"draft": [("readonly", False)]},
            readonly=True,
            copy=False,
        ),
        "contract_start_task": fields.date(
            "Task Start",
            states={"draft": [("readonly", False)]},
            help="Start of first task",
            readonly=True,
            copy=False,
        ),
        "contract_name": fields.char(
            "Contract Name",
            states={"draft": [("readonly", False)]},
            readonly=True,
            copy=False,
        ),
        "contract_id": fields.many2one(
            "account.analytic.account",
            "Contract",
            readonly=True,
            copy=False,
            ondelete="set null",
        ),
    }
