# -*- coding: utf-8 -*-
{
    "name": "Wellhub / Asaas",
    "summary": "Colaboradores Wellhub e assinaturas recorrentes no Asaas",
    "version": "18.0.1.7.1",
    "category": "Services",
    "author": "AFR",
    "license": "LGPL-3",
    "depends": ["website", "mail"],
    "external_dependencies": {"python": ["requests"]},
    "assets": {
        "web.assets_frontend": [
            "afr_wellhub/static/src/scss/portal_wellhub.scss",
            "afr_wellhub/static/src/js/portal_wellhub_inscricao.js",
        ],
    },
    "data": [
        "security/wellhub_security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "data/mail_template_data.xml",
        "views/wellhub_asaas_payment_views.xml",
        "views/wellhub_collaborator_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
        "views/portal_wellhub_templates.xml",
        "data/website_menu.xml",
    ],
    "installable": True,
    "application": True,
}
