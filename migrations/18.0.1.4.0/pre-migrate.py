# -*- coding: utf-8 -*-
"""Antes do ORM atualizar o esquema: cria ``wellhub_subscription_enrolled`` e copia o antigo
boolean ``wellhub_subscription_active`` (contrato no Asaas), preservando o estado ao passar
o campo «ativa» a ser calculado com base em cobrança paga.
"""


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'wellhub_collaborator'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'wellhub_collaborator'
          AND column_name = 'wellhub_subscription_enrolled'
        """
    )
    if not cr.fetchone():
        cr.execute(
            """
            ALTER TABLE wellhub_collaborator
            ADD COLUMN wellhub_subscription_enrolled boolean DEFAULT false
            """
        )
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'wellhub_collaborator'
          AND column_name = 'wellhub_subscription_active'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE wellhub_collaborator
        SET wellhub_subscription_enrolled = COALESCE(wellhub_subscription_active, false)
        """
    )
