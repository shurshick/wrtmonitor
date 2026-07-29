from backend.app.services.management_options import build_management_options


def test_management_options_are_derived_from_router_telemetry() -> None:
    result = build_management_options(
        {
            "network": {
                "interfaces": [
                    {"interface": "lan", "device": "br-lan"},
                    {"interface": "wan", "device": "eth1"},
                ],
                "firewall_zones": [{"name": "lan"}, {"name": "wan"}],
                "topology": {"bridges": [{"name": "br-lan"}]},
            },
            "wifi": {
                "available": True,
                "radios": [
                    {
                        "id": "radio1",
                        "name": "phy1",
                        "band": "5g",
                        "channel": "36",
                        "country": "RU",
                        "htmode": "HE80",
                        "supported_channels": ["auto", "36", "40"],
                    }
                ],
            },
        }
    )

    assert result["source"] == "router-telemetry"
    assert result["interfaces"] == ["br-lan", "eth1", "lan", "wan"]
    assert result["firewall_zones"] == ["lan", "wan"]
    assert result["bridges"] == ["br-lan"]
    assert result["wifi_radios"][0] == {
        "id": "radio1",
        "name": "phy1",
        "band": "5g",
        "channel": "36",
        "country": "RU",
        "htmode": "HE80",
        "supported_channels": ["auto", "36", "40"],
    }
    assert (
        next(
            item
            for item in result["catalogs"]["wifi_countries"]
            if item["value"] == "RU"
        )["observed"]
        is True
    )


def test_management_options_do_not_invent_router_objects_without_telemetry() -> None:
    result = build_management_options({})

    assert result["interfaces"] == []
    assert result["firewall_zones"] == []
    assert result["wifi_radios"] == []
