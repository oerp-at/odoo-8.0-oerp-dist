# -*- coding: utf-8 -*-
# -*- encoding: utf-8 -*-

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


class product_template(osv.osv):

    _inherit = "product.template"
    _columns = {
        "commission_percent": fields.related(
            "product_variant_ids", "commission_percent", string="Commission %"
        ),
        "commission_prod_id": fields.related(
            "product_variant_ids",
            "commission_prod_id",
            type="many2one",
            obj="product.product",
            string="Commission Product",
        ),
    }


class product_product(osv.osv):

    _inherit = "product.product"
    _columns = {
        "commission_percent": fields.float("Commission %"),
        "commission_prod_id": fields.many2one("product.product", "Commission Product"),
    }


class product_category(osv.osv):

    _inherit = "product.category"
    _columns = {
        "commission_percent": fields.float("Commission %"),
        "commission_prod_id": fields.many2one("product.product", "Commission Product"),
    }
