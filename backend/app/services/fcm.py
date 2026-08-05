import json
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import PushToken


logger = logging.getLogger(__name__)

_firebase_app = None


def init_firebase(config: Settings):
    global _firebase_app
    if not config.enable_push_notifications or not config.fcm_credentials_json:
        logger.info("Push notifications are disabled or FCM credentials missing.")
        return

    try:
        cred_dict = json.loads(config.fcm_credentials_json)
        cred = credentials.Certificate(cred_dict)
        _firebase_app = firebase_admin.initialize_app(cred, name="wrtmonitor")
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")


def send_push_notification(db: Session, user_id, title: str, body: str, data: dict = None) -> int:
    """
    Sends a push notification to all registered tokens for the given user.
    Returns the number of successful deliveries.
    """
    global _firebase_app
    if not _firebase_app:
        return 0

    tokens = db.scalars(select(PushToken.token).where(PushToken.user_id == user_id)).all()
    if not tokens:
        return 0

    success_count = 0
    invalid_tokens = []
    
    # Firebase MulticastMessage limit is 500 tokens
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
        tokens=list(tokens)[:500]
    )

    try:
        response = messaging.send_each_for_multicast(message, app=_firebase_app)
        success_count = response.success_count

        if response.failure_count > 0:
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    if resp.exception and resp.exception.code in (
                        'messaging/invalid-registration-token',
                        'messaging/registration-token-not-registered'
                    ):
                        invalid_tokens.append(tokens[idx])
        
        # Cleanup invalid tokens
        if invalid_tokens:
            db.execute(
                PushToken.__table__.delete().where(PushToken.token.in_(invalid_tokens))
            )
            db.commit()
            logger.info(f"Removed {len(invalid_tokens)} invalid FCM tokens for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send push notification to user {user_id}: {e}")

    return success_count


def send_push_notification_to_all(db: Session, title: str, body: str, data: dict = None) -> int:
    """
    Sends a push notification to all registered tokens across all users.
    """
    global _firebase_app
    if not _firebase_app:
        return 0

    tokens = db.scalars(select(PushToken.token)).all()
    if not tokens:
        return 0

    success_count = 0
    invalid_tokens = []
    
    # Simple chunking for multicast limit (up to 500)
    tokens_list = list(tokens)
    for i in range(0, len(tokens_list), 500):
        chunk = tokens_list[i:i+500]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=chunk
        )
        try:
            response = messaging.send_each_for_multicast(message, app=_firebase_app)
            success_count += response.success_count
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success and resp.exception and resp.exception.code in (
                        'messaging/invalid-registration-token',
                        'messaging/registration-token-not-registered'
                    ):
                        invalid_tokens.append(chunk[idx])
        except Exception as e:
            logger.error(f"Failed to send push notification broadcast chunk: {e}")

    if invalid_tokens:
        db.execute(PushToken.__table__.delete().where(PushToken.token.in_(invalid_tokens)))
        db.commit()

    return success_count
