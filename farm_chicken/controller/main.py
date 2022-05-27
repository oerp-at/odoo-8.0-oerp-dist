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

from openerp.addons.web import http
import logging
import werkzeug.utils

_logger = logging.getLogger(__name__)

class chicken_farm(http.Controller):
    
    @http.route(["/farm/chicken"], type="http", auth="public")
    def app_redirect(self, debug=False, **kwargs):
        if debug:
            return werkzeug.utils.redirect("/farm_chicken/static/src/index.html?debug")
        else:
            return werkzeug.utils.redirect("/farm_chicken/static/app/index.html")