from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    DEEPSEEK_API_KEY:str
    MODEL_PROVIDER: str
    MODEL_NAME:str="deepseek-chat"

    BASE_URL: str = "https://api.deepseek.com"

    class Config:

        env_file=".env"



settings = Settings()