import unittest

from fast_flights.querying import FlightQuery, create_query


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0

    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7


def _top_level_fields(data: bytes) -> list[int]:
    fields: list[int] = []
    i = 0

    while i < len(data):
        key, i = _read_varint(data, i)
        field = key >> 3
        wire_type = key & 0x07
        fields.append(field)

        if wire_type == 0:
            _, i = _read_varint(data, i)
        elif wire_type == 2:
            length, i = _read_varint(data, i)
            i += length
        else:
            raise ValueError(f"Unsupported wire type in test parser: {wire_type}")

    return fields


class QueryTests(unittest.TestCase):
    def test_exclude_basic_adds_field_25(self) -> None:
        query = create_query(
            flights=[
                FlightQuery(
                    date="2026-04-15",
                    from_airport="LAX",
                    to_airport="AUS",
                ),
            ],
            seat="economy",
            exclude_basic=True,
        )

        fields = _top_level_fields(query.to_bytes())
        self.assertIn(25, fields)

    def test_default_query_does_not_add_field_25(self) -> None:
        query = create_query(
            flights=[
                FlightQuery(
                    date="2026-04-15",
                    from_airport="LAX",
                    to_airport="AUS",
                ),
            ],
            seat="economy",
        )

        fields = _top_level_fields(query.to_bytes())
        self.assertNotIn(25, fields)

    def test_exclude_basic_rejects_non_economy(self) -> None:
        with self.assertRaises(ValueError):
            create_query(
                flights=[
                    FlightQuery(
                        date="2026-04-15",
                        from_airport="LAX",
                        to_airport="AUS",
                    ),
                ],
                seat="business",
                exclude_basic=True,
            )


if __name__ == "__main__":
    unittest.main()
