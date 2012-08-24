import copy

from . import six


# Used to control how many objects are worked with at once in some cases (e.g.
# when deleting objects).
CHUNK_SIZE = 100
ITER_CHUNK_SIZE = CHUNK_SIZE

# The maximum number of items to display in a QuerySet.__repr__
REPR_OUTPUT_SIZE = 20


class Empty(object):
    pass


class Query(object):
    """
    A single API query.
    """

    def __init__(self, resource, *args, **kwargs):
        super(Query, self).__init__(*args, **kwargs)

        self.resource = resource

        self.filters = {}
        self.order_by = None

        self.low_mark = 0
        self.high_mark = None

    def clone(self, klass=None, memo=None, **kwargs):
        """
        Creates a copy of the current instance. The 'kwargs' parameter can be
        used by clients to update attributes after copying has taken place.
        """
        obj = Empty()
        obj.__class__ = klass or self.__class__

        obj.resource = self.resource

        obj.filters = self.filters.copy()
        obj.order_by = self.order_by

        obj.low_mark = self.low_mark
        obj.high_mark = self.high_mark

        obj.__dict__.update(kwargs)

        return obj

    def add_filters(self, **filters):
        """
        Adjusts the filters that should be applied to the request to the API.
        """
        self.filters.update(filters)

    def add_ordering(self, ordering=None):
        """
        Adds items from the 'ordering' sequence to the query's "order by"
        clause. These items are either field names (not column names) --
        possibly with a direction prefix ('-').

        If 'ordering' is empty, all ordering is cleared from the query.
        """
        if ordering is not None:
            self.order_by = ordering
        else:
            self.clear_ordering()

    def clear_ordering(self):
        """
        Removes any ordering settings.
        """
        self.order_by = None

    def set_limits(self, low=None, high=None):
        """
        Adjusts the limits on the rows retrieved. We use low/high to set these,
        as it makes it more Pythonic to read and write. When the API query is
        created, they are converted to the appropriate offset and limit values.

        Any limits passed in here are applied relative to the existing
        constraints. So low is added to the current low value and both will be
        clamped to any existing high value.
        """
        if high is not None:
            if self.high_mark is not None:
                self.high_mark = min(self.high_mark, self.low_mark + high)
            else:
                self.high_mark = self.low_mark + high
        if low is not None:
            if self.high_mark is not None:
                self.low_mark = min(self.high_mark, self.low_mark + low)
            else:
                self.low_mark = self.low_mark + low

    def results(self, limit=100):
        """
        Yields the results from the API, efficiently handling the pagination and
        properly passing all paramaters.
        """
        limited = True if self.high_mark is not None else False
        rmax = self.high_mark - self.low_mark if limited else None
        rnum = 0

        params = self.get_params()
        params["offset"] = self.low_mark
        params["limit"] = limit

        while not limited and rmax is None or rnum < rmax:
            if limited or rmax is not None:
                rleft = rmax - rnum
                params["limit"] = rleft if rleft < limit else limit

            r = self.resource._meta.api.http_resource("GET", self.resource._meta.resource_name, params=params)
            data = self.resource._meta.api.resource_deserialize(r.text)

            if not limited:
                rmax = data["meta"]["total_count"]

            if data["meta"]["total_count"] < rmax:
                rmax = data["meta"]["total_count"]

            params["offset"] = data["meta"]["offset"] + data["meta"]["limit"]

            for item in data["objects"]:
                rnum += 1
                yield item

    def delete(self):
        """
        Deletes the results of this query, it first fetches all the items to be
        deletes and then issues a PATCH against the list uri of the resource.
        """
        uris = [obj.resource_uri for obj in self.results()]
        self.resource._meta.api.http_resource("PATCH", self.resource._meta.resource_name, data={"objects": [], "deleted_objects": uris})
        return len(uris)

    def get_params(self):
        params = {}

        # Apply filters
        params.update(self.filters)

        # Apply Ordering
        if self.order_by is not None:
            params["order_by"] = self.order_by

        return params

    def get_count(self):
        """
        Gets the total_count using the current filter constraints.
        """
        params = self.get_params()
        params["offset"] = self.low_mark
        params["limit"] = 1

        r = self.resource._meta.api.http_resource("GET", self.resource._meta.resource_name, params=params)
        data = self.resource._meta.api.resource_deserialize(r.text)

        number = data["meta"]["total_count"]

        # Apply offset and limit constraints manually, since using limit/offset
        # in the API doesn't change the total_count output.
        number = max(0, number - self.low_mark)
        if self.high_mark is not None:
            number = min(number, self.high_mark - self.low_mark)

        return number

    def can_filter(self):
        """
        Returns True if adding filters to this instance is still possible.

        Typically, this means no limits or offsets have been put on the results.
        """
        return not self.low_mark and self.high_mark is None

    def has_results(self):
        q = self.clone()
        q.clear_ordering()
        q.set_limits(high=1)

        return bool(list(q.results()))


class QuerySet(object):
    """
    Represents a lazy api lookup for a set of objects.
    """

    def __init__(self, resource, query=None, *args, **kwargs):
        super(QuerySet, self).__init__(*args, **kwargs)

        self.resource = resource
        self.query = query or Query(self.resource)

        self._result_cache = None
        self._iter = None

    ########################
    # PYTHON MAGIC METHODS #
    ########################

    def __deepcopy__(self, memo):
        """
        Deep copy of a QuerySet doesn't populate the cache
        """
        obj = self.__class__()
        for k, v in six.iteritems(self.__dict__):
            if k in ("_iter", "_result_cache"):
                obj.__dict__[k] = None
            else:
                obj.__dict__[k] = copy.deepcopy(v, memo)
        return obj

    def __getstate__(self):
        """
        Allows the QuerySet to be pickled.
        """
        # Force the cache to be fully populated.
        len(self)

        obj_dict = self.__dict__.copy()
        obj_dict["_iter"] = None

        return obj_dict

    def __repr__(self):
        data = list(self[:REPR_OUTPUT_SIZE + 1])

        if len(data) > REPR_OUTPUT_SIZE:
            data[-1] = "...(remaining elements truncated)..."

        return repr(data)

    def __len__(self):
        # Since __len__ is called quite frequently (for example, as part of
        # list(qs), we make some effort here to be as efficient as possible
        # whilst not messing up any existing iterators against the QuerySet.
        if self._result_cache is None:
            if self._iter:
                self._result_cache = list(self._iter)
            else:
                self._result_cache = list(self.iterator())
        elif self._iter:
            self._result_cache.extend(self._iter)

        return len(self._result_cache)

    def __iter__(self):
        if self._result_cache is None:
            self._iter = self.iterator()
            self._result_cache = []

        if self._iter:
            return self._result_iter()

        # Python's list iterator is better than our version when we're just
        # iterating over the cache.
        return iter(self._result_cache)

    def __nonzero__(self):
        if self._result_cache is not None:
            return bool(self._result_cache)

        try:
            next(iter(self))
        except StopIteration:
            return False

        return True

    def __getitem__(self, k):
        """
        Retrieves an item or slice from the set of results.
        """

        if not isinstance(k, (slice,) + six.integer_types):
            raise TypeError

        assert ((not isinstance(k, slice) and (k >= 0))
                or (isinstance(k, slice) and (k.start is None or k.start >= 0)
                    and (k.stop is None or k.stop >= 0))), \
                "Negative indexing is not supported."

        if self._result_cache is not None:
            if self._iter is not None:
                # The result cache has only been partially populated, so we may
                # need to fill it out a bit more.
                if isinstance(k, slice):
                    if k.stop is not None:
                        # Some people insist on passing in strings here.
                        bound = int(k.stop)
                    else:
                        bound = None
                else:
                    bound = k + 1

                if len(self._result_cache) < bound:
                    self._fill_cache(bound - len(self._result_cache))
            return self._result_cache[k]

        if isinstance(k, slice):
            qs = self._clone()

            if k.start is not None:
                start = int(k.start)
            else:
                start = None
            if k.stop is not None:
                stop = int(k.stop)
            else:
                stop = None

            qs.query.set_limits(start, stop)

            return k.step and list(qs)[::k.step] or qs

        qs = self._clone()
        qs.query.set_limits(k, k + 1)
        return list(qs)[0]

    ###############################
    # METHODS THAT DO API QUERIES #
    ###############################

    def iterator(self):
        """
        An iterator over the results from applying this QuerySet to the api.
        """

        for item in self.query.results():
            obj = self.resource(**item)

            yield obj

    def count(self):
        """
        Returns the number of records as an integer.

        If the QuerySet is already fully cached this simply returns the length
        of the cached results set to avoid an api call.
        """
        if self._result_cache is not None and not self._iter:
            return len(self._result_cache)

        return self.query.get_count()

    def get(self, *args, **kwargs):
        """
        Performs the query and returns a single object matching the given
        keyword arguments.
        """
        clone = self.filter(*args, **kwargs)

        if self.query.can_filter():
            clone = clone.order_by()

        num = len(clone)

        if num == 1:
            return clone._result_cache[0]
        if not num:
            raise self.resource.DoesNotExist(
                "%s matching query does not exist. "
                "Lookup parameters were %s" %
                (self.resource._meta.resource_name, kwargs))

        raise self.resource.MultipleObjectsReturned(
            "get() returned more than one %s -- it returned %s! "
            "Lookup parameters were %s" %
            (self.resource._meta.resource_name, num, kwargs))

    def create(self, **kwargs):
        """
        Creates a new object with the given kwargs, saving it to the api
        and returning the created object.
        """
        obj = self.resource(**kwargs)
        obj.save(force_insert=True)
        return obj

    def get_or_create(self, **kwargs):
        """
        Looks up an object with the given kwargs, creating one if necessary.
        Returns a tuple of (object, created), where created is a boolean
        specifying whether an object was created.
        """
        assert kwargs, "get_or_create() must be passed at least one keyword argument"

        defaults = kwargs.pop("defaults", {})
        lookup = kwargs.copy()

        try:
            return self.get(**lookup), False
        except self.resource.DoesNotExist:
            params = dict([(k, v) for k, v in kwargs.items()])
            params.update(defaults)

            obj = self.create(**params)
            return obj, True

    def delete(self):
        """
        Deletes the records in the current QuerySet.
        """
        assert self.query.can_filter(), "Cannot use 'limit' or 'offset' with delete."

        del_query = self._clone()

        # Disable non-supported fields.
        del_query.query.clear_ordering()

        return del_query.query.delete()

    def exists(self):
        if self._result_cache is None:
            return self.query.has_results()
        return bool(self._result_cache)

    ##################################################################
    # PUBLIC METHODS THAT ALTER ATTRIBUTES AND RETURN A NEW QUERYSET #
    ##################################################################

    def all(self):
        """
        Returns a new QuerySet that is a copy of the current one.
        """
        return self._clone()

    def filter(self, **kwargs):
        """
        Returns a new QuerySet instance with the args ANDed to the existing
        set.
        """
        if kwargs:
            assert self.query.can_filter(), "Cannot filter a query once a slice has been taken."

        clone = self._clone()
        clone.query.add_filters(**kwargs)

        return clone

    def order_by(self, field_name=None):
        """
        Returns a new QuerySet instance with the ordering changed.
        """
        assert self.query.can_filter(), "Cannot reorder a query once a slice has been taken."

        clone = self._clone()
        clone.query.clear_ordering()

        if field_name is not None:
            clone.query.add_ordering(field_name)

        return clone

    ###################################
    # PUBLIC INTROSPECTION ATTRIBUTES #
    ###################################

    @property
    def ordered(self):
        """
        Returns True if the QuerySet is ordered -- i.e. has an order_by()
        clause.
        """
        if self.query.order_by:
            return True
        else:
            return False

    ###################
    # PRIVATE METHODS #
    ###################

    def _result_iter(self):
        pos = 0

        while True:
            upper = len(self._result_cache)

            while pos < upper:
                yield self._result_cache[pos]
                pos += 1

            if not self._iter:
                raise StopIteration

            if len(self._result_cache) <= pos:
                self._fill_cache()

    def _fill_cache(self, num=None):
        """
        Fills the result cache with 'num' more entries (or until the results
        iterator is exhausted).
        """
        if self._iter:
            try:
                for i in range(num or ITER_CHUNK_SIZE):
                    self._result_cache.append(next(self._iter))
            except StopIteration:
                self._iter = None

    def _clone(self, klass=None, setup=False, **kwargs):
        if klass is None:
            klass = self.__class__

        query = self.query.clone()

        c = klass(resource=self.resource, query=query)
        c.__dict__.update(kwargs)

        return c
