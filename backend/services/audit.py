import json
import logging
from datetime import datetime
from db import DB

logger = logging.getLogger("food_court.audit")


class AuditService:
    """
    Centralized administrative and operational audit logging service.
    Records security-sensitive actions and operational transitions to the `audit_logs` table.
    """

    @staticmethod
    def log_action(actor_id, action, entity_type, entity_id=None, details=None, tx=None):
        """
        Records an audit event.
        - actor_id: ID of the user performing the action.
        - action: Canonical action code, e.g. 'SHOP_CREATED', 'ORDER_STATUS_CHANGED'.
        - entity_type: The subject entity, e.g. 'shop', 'order', 'menu_item', 'user'.
        - entity_id: Identifier of the subject entity (string or int).
        - details: Freeform text or dict/list with contextual data (auto JSON-serialized).
        - tx: Optional active DB transaction context.
        """
        if not actor_id or not action or not entity_type:
            logger.warning("AuditService.log_action called with missing required parameters.")
            return None

        details_str = None
        if details is not None:
            if isinstance(details, (dict, list)):
                try:
                    details_str = json.dumps(details)
                except Exception as e:
                    details_str = str(details)
            else:
                details_str = str(details)

        entity_id_str = str(entity_id) if entity_id is not None else None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        query = """
            INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (actor_id, action, entity_type, entity_id_str, details_str, now_str)

        try:
            if tx:
                return tx.execute(query, params)
            return DB.execute(query, params)
        except Exception as e:
            logger.error("Failed to write audit log for action=%s entity_type=%s: %s", action, entity_type, e)
            return None
