import logging

from django.db import transaction

logger = logging.getLogger(__name__)

RETRY_TASK = 'accounts.tasks.delete_stored_file'


def delete_file_field(instance, field_name):
    """
    Removes the file behind a FileField/ImageField once the deletion commits.
    Meant to be called from a post_delete signal receiver rather than a model
    delete() override — Django's cascade-delete collector bulk-deletes rows
    via raw SQL without calling each instance's Python delete() method, so
    an override would silently skip cleanup on cascade deletes (e.g.
    deleting a User that cascades through to a founder's Application).
    post_delete fires per-instance on every deletion path, including those.

    The removal waits for the commit, so a deletion that rolls back never loses
    its files, and a storage failure never undoes a deletion that has already
    committed: it is logged to ops.FailedTaskLog as accounts.tasks.delete_stored_file,
    which staff can requeue from the ops dashboard.
    """
    file_obj = getattr(instance, field_name, None)
    if not file_obj:
        return
    storage, name = file_obj.storage, file_obj.name
    transaction.on_commit(lambda: _delete_stored_file(storage, name))


def _delete_stored_file(storage, name):
    try:
        storage.delete(name)
    except Exception as exc:
        logger.exception("Could not remove a stored file after its deletion committed; logged for retry")
        from ops.models import log_failed_task
        log_failed_task(RETRY_TASK, [name], exc.__class__.__name__)
