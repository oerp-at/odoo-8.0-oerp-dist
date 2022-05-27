#############################################################################
#
#    Copyright (c) 2007 Martin Reisenhofer <martinr@funkring.net>
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
{
    "name": "oerp.at Sale",
    "description": """
oerp.at Sale Extensions
=======================

* Invoice <-> Sale link
* CRM category code
* More informational invoice line
* Aeroo report replacement
* Shop for picking

""",
    "version": "1.1",
    "author": "funkring.net",
    "website": "http://www.funkring.net",
    "category": "Sales",
    "depends": [
        "account",
        "sale",
        "sale_crm",
        "sale_stock",
        "at_base",
        "at_product",
        "at_account",
        "at_resource",
        "at_procurement",
        "at_product",
        "at_stock",
        "at_crm",
    ],
    "data": [
        "view/partner_view.xml",
        "security.xml",
        "view/shop_view.xml",
        "view/sale_view.xml",
        "view/sale_tree_view.xml",
        "view/stock_picking_view.xml",
        "view/product_view.xml",
        "view/invoice_view.xml",
        "report/sale_order_report.xml",
    ],
    "auto_install": False,
    "installable": True,
}
