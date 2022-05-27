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

{
    "name" : "Sale dynamic Bill of Material",
    "summary" : "Create dynamic MRP order from sale order",
    "description":"""
Dynamic Bill of Material
========================
* Create dynamic MRP order from sale order
    """,
    "version" : "1.0",
    "author" :  "oerp.at",
    "website" : "http://oerp.at",
    "category" : "Sales",
    "depends" : ["mrp",
                 "at_mrp", 
                 "sale",
                 "at_sale",
                 "at_purchase_sale" ],
    "data" : ["view/product_view.xml",
              "view/sale_view.xml",
              "view/stock_view.xml",
              "view/mrp_view.xml"],
    "auto_install" : False,
    "installable": True
}