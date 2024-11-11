from feed_proxy.handlers import HandlerType, get_registered_handlers


def parse_configuration() -> dict:
    handlers = get_registered_handlers()
    results: dict = {"handlers": {}}

    for item in HandlerType:
        results["handlers"][item.value] = [
            {
                "type": name,
                "options": dict(opt.to_json_schema()) if opt else {},
                "return_fields_schema": f_schema,
            }
            for name, _, opt, f_schema, _ in handlers[item.value].values()
        ]

    return results
