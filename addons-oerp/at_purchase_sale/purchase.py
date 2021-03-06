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
from openerp.tools.translate import _
from openerp.tools.float_utils import float_compare


class purchase_order(osv.osv):

    #     def do_merge(self, cr, uid, ids, context=None):
    #         for order in self.browse(cr, uid, ids, context=context):
    #             if order.sale_order_id:
    #                 raise osv.except_osv(_("Error"), _("A purchase order linked with an sale order cannot be merged!"))
    #         return super(purchase_order, self).do_merge(cr, uid, ids, context=context)

    def _prepare_order_line_move(
        self, cr, uid, order, order_line, picking_id, group_id, context=None
    ):
        """ prepare the stock move data from the PO line. This function returns a list of dictionary ready to be used in stock.move's create()
            inherited from purchase/purchase.py
        """

        # override group_id if sale order and a procurement group exist
        if order.sale_order_id and order.sale_order_id.procurement_group_id:
            group_id = order.sale_order_id.procurement_group_id.id

        product_uom = self.pool.get("product.uom")
        price_unit = order_line.price_unit
        if order_line.product_uom.id != order_line.product_id.uom_id.id:
            price_unit *= (
                order_line.product_uom.factor / order_line.product_id.uom_id.factor
            )
        if order.currency_id.id != order.company_id.currency_id.id:
            # we don't round the price_unit, as we may want to store the standard price with more digits than allowed by the currency
            price_unit = self.pool.get("res.currency").compute(
                cr,
                uid,
                order.currency_id.id,
                order.company_id.currency_id.id,
                price_unit,
                round=False,
                context=context,
            )
        res = []

        if order.location_id.usage == "customer":
            # check direct link with sale order
            sale_line = order_line.sale_line_id
            if sale_line:
                name = sale_line.name
            else:
                # check if linked over procurement
                description = []
                for proc in order_line.procurement_ids:
                    sale_line = proc.sale_line_id
                    if sale_line:
                        description.append(sale_line.name)

                if description:
                    name = "\n".join(description)
                else:
                    # default product description
                    name = order_line.product_id.with_context(
                        dict(context or {}, lang=order.dest_address_id.lang)
                    ).name
        else:
            name = order_line.name or ""

        move_template = {
            "name": name,
            "product_id": order_line.product_id.id,
            "product_uom": order_line.product_uom.id,
            "product_uos": order_line.product_uom.id,
            "date": order.date_order,
            "date_expected": fields.date.date_to_datetime(
                self, cr, uid, order_line.date_planned, context
            ),
            "location_id": order.partner_id.property_stock_supplier.id,
            "location_dest_id": order.location_id.id,
            "picking_id": picking_id,
            "partner_id": order.dest_address_id.id,
            "move_dest_id": False,
            "state": "draft",
            "purchase_line_id": order_line.id,
            "company_id": order.company_id.id,
            "price_unit": price_unit,
            "picking_type_id": order.picking_type_id.id,
            "group_id": group_id,
            "procurement_id": False,
            "origin": order.name,
            "route_ids": order.picking_type_id.warehouse_id
            and [(6, 0, [x.id for x in order.picking_type_id.warehouse_id.route_ids])]
            or [],
            "warehouse_id": order.picking_type_id.warehouse_id.id,
            "invoice_state": order.invoice_method == "picking"
            and "2binvoiced"
            or "none",
        }

        diff_quantity = order_line.product_qty
        for procurement in order_line.procurement_ids:
            procurement_qty = product_uom._compute_qty(
                cr,
                uid,
                procurement.product_uom.id,
                procurement.product_qty,
                to_uom_id=order_line.product_uom.id,
            )
            tmp = move_template.copy()
            tmp.update(
                {
                    "product_uom_qty": min(procurement_qty, diff_quantity),
                    "product_uos_qty": min(procurement_qty, diff_quantity),
                    "move_dest_id": procurement.move_dest_id.id,  # move destination is same as procurement destination
                    "group_id": procurement.group_id.id
                    or group_id,  # move group is same as group of procurements if it exists, otherwise take another group
                    "procurement_id": procurement.id,
                    "invoice_state": procurement.rule_id.invoice_state
                    or (
                        procurement.location_id
                        and procurement.location_id.usage == "customer"
                        and procurement.invoice_state == "2binvoiced"
                        and "2binvoiced"
                    )
                    or (order.invoice_method == "picking" and "2binvoiced")
                    or "none",  # dropship case takes from sale
                    "propagate": procurement.rule_id.propagate,
                }
            )
            diff_quantity -= min(procurement_qty, diff_quantity)
            res.append(tmp)
        # if the order line has a bigger quantity than the procurement it was for (manually changed or minimal quantity), then
        # split the future stock move in two because the route followed may be different.
        if (
            float_compare(
                diff_quantity, 0.0, precision_rounding=order_line.product_uom.rounding
            )
            > 0
        ):
            move_template["product_uom_qty"] = diff_quantity
            move_template["product_uos_qty"] = diff_quantity
            res.append(move_template)
        return res

    _inherit = "purchase.order"
    _columns = {
        "sale_order_id": fields.many2one(
            "sale.order",
            "Sale Order",
            states={
                "confirmed": [("readonly", True)],
                "approved": [("readonly", True)],
                "done": [("readonly", True)],
            },
            ondelete="set null",
            copy=False,
        ),
        "shop_id": fields.related(
            "sale_order_id",
            "shop_id",
            type="many2one",
            relation="sale.shop",
            string="Shop",
            readonly=True,
            store=False,
            select=True,
        ),
    }


class purchase_order_line(osv.osv):

    _inherit = "purchase.order.line"
    _columns = {
        "sale_line_id": fields.many2one(
            "sale.order.line",
            "Sale Order Line",
            readonly=True,
            copy=False,
            ondelete="set null",
        ),
    }
