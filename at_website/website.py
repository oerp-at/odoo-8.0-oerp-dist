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

from openerp.osv import orm, osv, fields
from openerp.addons.web.http import request
import uuid


class website_menu(osv.osv):
    _inherit = "website.menu"
    _columns = {
        "inv_header": fields.boolean("Invisible in Header"),
        "inv_footer": fields.boolean("Invisible in Footer"),
    }


class website(osv.osv):
    _inherit = "website"

    def create_uuid(self, **kwargs):
        return uuid.uuid4()

    def get_language(self, cr, uid, ids, context=None):
        lang_first = None
        lang_default = None

        lang = request.context.get("lang")
        website = self.browse(cr, uid, ids[0])
        for lang_data in self._get_languages(cr, uid, website.id):
            if lang == lang_data[0]:
                return lang_data
            if not lang_default and website.default_lang_code == lang_data[0]:
                lang_default = lang_data
            if not lang_first:
                lang_first = lang_data
        return lang_default or lang_first

    _inherit = "website"
