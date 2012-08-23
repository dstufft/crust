class Field(object):
    """
    Base class for all field types
    """

    # This tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self, name=None, primary_key=False, serialize=True, *args, **kwargs):
        super(Field, self).__init__(*args, **kwargs)

        self.name = name
        self.primary_key = primary_key
        self.serialize = serialize

        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

    def hydrate(self, value):
        return value