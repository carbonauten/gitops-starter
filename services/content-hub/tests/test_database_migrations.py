from app.database import scheduled_publish_column_type


def test_scheduled_publish_column_type_for_postgres():
    assert scheduled_publish_column_type(False) == "TIMESTAMP WITH TIME ZONE"
    assert scheduled_publish_column_type(True) == "DATETIME"
