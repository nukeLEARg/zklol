from InsightSubsystems.Cache.Clients.AbstractBaseClient import AbstractBaseClient
import redis
import time
import traceback
import InsightExc


class RedisClient(AbstractBaseClient):
    def __init__(self, config_class, concurrent_pool):
        super().__init__(config_class, concurrent_pool)
        self.host = self.config.get("REDIS_HOST")
        self.password = self.config.get("REDIS_PASSWORD")
        self.port = self.config.get("REDIS_PORT")
        self.db = self.config.get("REDIS_DB")
        self.purge_keys = self.config.get("REDIS_PURGE")
        self.timeout = self.config.get("REDIS_TIMEOUT")
        self.ssl = True if self.config.get("REDIS_SSL") else None
        self.max_connections = self.config.get("REDIS_CONNECTIONS_MAX")
        self.client = None

    async def establish_connection(self):
        if self.host == "":
            print("No Redis host is defined. Functions requiring Redis will not function until a valid instance is "
                  "provided.")
            return False
        try:
            self.client = await redis.asyncio.from_url(
                f"redis://:{self.password}@{self.host}:{self.port}/{self.db}",
                socket_connect_timeout=self.timeout,
                max_connections=self.max_connections,
                decode_responses=True)
            test_ok = await self.test_connection()
            if test_ok:
                return True
            else:
                return False
        except Exception as ex:
            traceback.print_exc()
            print("Error when attempting to establish a connection to the Redis host: redis://{}:{}. Insight will "
                  "operate without Redis and all functions that require Redis will not work.".format(self.host,
                                                                                                     self.port))
            return False

    async def test_connection(self):
        current_time = {"time": time.time()}
        await self.client.set("test_time", await self.serialize(current_time),ex=5)
        cache_time = await self.deserialize(await self.client.get("test_time"))
        if current_time != cache_time:
            return False
        else:
            return True

    async def get(self, key_str: str) -> dict:
        result = await self.client.get(key_str)
        if result is None:
            raise InsightExc.Subsystem.KeyDoesNotExist
        else:
            return await self.deserialize(result)

    async def set(self, key_str: str, ttl: int, data_dict: dict):
        value_to_set = await self.serialize(data_dict)
        await self.client.set(key_str, value_to_set, ex=ttl)

    async def get_ttl(self, key_str: str) -> int:
        ttl = await self.client.ttl(key_str)
        if ttl == -2:
            raise InsightExc.Subsystem.KeyDoesNotExist
        return ttl

    async def delete(self, key_str: str):
        await self.client.delete(key_str)

    async def redis_purge_all_keys(self):
        await self.client.flushdb()
        print("All keys in Redis database '{}' have been purged.".format(self.db))

