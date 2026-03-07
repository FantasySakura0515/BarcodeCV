import uvicorn

from ..utils.config_loader import load_config


def main() -> None:
    config = load_config()
    api_config = config.get("api", {})
    uvicorn.run(
        "backend.api.main:app",
        host=api_config.get("host", "0.0.0.0"),
        port=int(api_config.get("port", 8000)),
        reload=False,
    )


if __name__ == "__main__":
    main()
