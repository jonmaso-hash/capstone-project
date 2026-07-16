def delete_file_field(instance, field_name):
    """
    Deletes the file backing a FileField/ImageField from storage. Meant to
    be called from a post_delete signal receiver rather than a model
    delete() override — Django's cascade-delete collector bulk-deletes rows
    via raw SQL without calling each instance's Python delete() method, so
    an override would silently skip cleanup on cascade deletes (e.g.
    deleting a User that cascades through to a founder's Application).
    post_delete fires per-instance on every deletion path, including those.
    """
    file_obj = getattr(instance, field_name, None)
    if file_obj:
        file_obj.storage.delete(file_obj.name)
