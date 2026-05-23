from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "OneASR"
    debug: bool = False
    default_engine: str = "whisper"
    max_file_size_mb: int = 500

    # Whisper 引擎配置
    whisper_model_size: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    model_config = {"env_prefix": "ONEASR_"}


settings = Settings()
