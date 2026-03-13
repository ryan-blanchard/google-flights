import json

from selectolax.lexbor import LexborHTMLParser

from .model import (
    Airline,
    Airport,
    Alliance,
    CarbonEmission,
    Flights,
    JsMetadata,
    SimpleDatetime,
    SingleFlight,
)


class MetaList(list[Flights]):
    """Searched flights list, with metadata attached."""

    metadata: JsMetadata


def parse(html: str) -> MetaList:
    parser = LexborHTMLParser(html)

    # find js
    script = parser.css_first(r"script.ds\:1")
    return parse_js(script.text())


# Data discovery by @kftang, huge shout out!
def parse_js(js: str):
    data = js.split("data:", 1)[1].rsplit(",", 1)[0]

    payload = json.loads(data)

    alliances = []
    airlines = []

    (alliances_data, airlines_data) = (
        payload[7][1][0],
        payload[7][1][1],
    )

    for code, name in alliances_data:
        alliances.append(Alliance(code=code, name=name))

    for code, name in airlines_data:
        airlines.append(Airline(code=code, name=name))

    meta = JsMetadata(alliances=alliances, airlines=airlines)

    flights = MetaList()

    def section_at(idx: int) -> list:
        if len(payload) <= idx or not isinstance(payload[idx], list) or not payload[idx]:
            return []

        section = payload[idx][0]
        return section if isinstance(section, list) else []

    top_flights = section_at(2)
    other_flights = section_at(3)

    if not top_flights and not other_flights:
        return flights

    # Newer payloads split results into "Top flights" (payload[2][0]) and
    # additional results (payload[3][0]). Keep both and deduplicate.
    sections = [
        *top_flights,
        *other_flights,
    ]
    seen: set[tuple] = set()

    for k in sections:
        if not k:
            continue

        flight = k[0]
        price = k[1][0][1]

        # Signature to avoid duplicates between top and additional sections.
        signature = (
            price,
            tuple(
                (
                    single_flight[3],  # from code
                    single_flight[6],  # to code
                    tuple(single_flight[8]),  # departure time
                    tuple(single_flight[20]),  # departure date
                    tuple(single_flight[10]),  # arrival time
                    tuple(single_flight[21]),  # arrival date
                )
                for single_flight in flight[2]
            ),
        )
        if signature in seen:
            continue
        seen.add(signature)

        typ = flight[0]
        airlines = flight[1]

        sg_flights = []

        # multiple flights!
        for single_flight in flight[2]:
            from_airport = Airport(code=single_flight[3], name=single_flight[4])
            to_airport = Airport(code=single_flight[6], name=single_flight[5])
            departure_time = single_flight[8]
            departure_date = single_flight[20]
            departure = SimpleDatetime(date=departure_date, time=departure_time)

            arrival_time = single_flight[10]
            arrival_date = single_flight[21]
            arrival = SimpleDatetime(date=arrival_date, time=arrival_time)

            plane_type = single_flight[17]

            duration = single_flight[11]
            marketing = single_flight[22] if len(single_flight) > 22 else None
            carrier_code = None
            carrier_name = None
            flight_number = None
            if isinstance(marketing, (list, tuple)):
                if len(marketing) > 0 and marketing[0]:
                    carrier_code = str(marketing[0]).strip().upper()
                if len(marketing) > 1 and marketing[1]:
                    flight_number = str(marketing[1]).strip()
                if len(marketing) > 3 and marketing[3]:
                    carrier_name = str(marketing[3]).strip()

            sg_flights.append(
                SingleFlight(
                    from_airport=from_airport,
                    to_airport=to_airport,
                    departure=departure,
                    arrival=arrival,
                    duration=duration,
                    plane_type=plane_type,
                    carrier_code=carrier_code or None,
                    carrier_name=carrier_name or None,
                    flight_number=flight_number or None,
                )
            )

        # some additional data
        extras = flight[22]
        carbon_emission = extras[7]
        typical_carbon_emission = extras[8]

        flights.append(
            Flights(
                type=typ,
                price=price,
                airlines=airlines,
                flights=sg_flights,
                carbon=CarbonEmission(
                    typical_on_route=typical_carbon_emission, emission=carbon_emission
                ),
            )
        )

    flights.metadata = meta
    return flights
