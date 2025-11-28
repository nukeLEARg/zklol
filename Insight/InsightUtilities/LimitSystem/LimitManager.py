from InsightUtilities.InsightSingleton import InsightSingleton
from InsightUtilities.ConfigLoader import ConfigLoader
from InsightUtilities.LimitSystem.LimitClient import LimitClient, LimitClientHP
import asyncio
import discord
import InsightExc
import traceback
from functools import partial

class LimitManager(metaclass=InsightSingleton):
    # The __init__ method is now VERY simple and purely synchronous.
    # It only sets up non-async attributes.
    def __init__(self):
        self.config: ConfigLoader = ConfigLoader()
        
        self.limit_global_sustain = self.config.get("LIMITER_GLOBAL_SUSTAIN_TICKETS")
        self.interval_global_sustain = self.config.get("LIMITER_GLOBAL_SUSTAIN_INTERVAL")
        self.limit_global_burst = self.config.get("LIMITER_GLOBAL_BURST_TICKETS")
        self.interval_global_burst = self.config.get("LIMITER_GLOBAL_BURST_INTERVAL")

        self.limit_dm_sustain = self.config.get("LIMITER_DM_SUSTAIN_TICKETS")
        self.interval_dm_sustain = self.config.get("LIMITER_DM_SUSTAIN_INTERVAL")
        self.limit_dm_burst = self.config.get("LIMITER_DM_BURST_TICKETS")
        self.interval_dm_burst = self.config.get("LIMITER_DM_BURST_INTERVAL")

        self.limit_user_sustain = self.config.get("LIMITER_USER_SUSTAIN_TICKETS")
        self.interval_user_sustain = self.config.get("LIMITER_USER_SUSTAIN_INTERVAL")
        self.limit_user_burst = self.config.get("LIMITER_USER_BURST_TICKETS")
        self.interval_user_burst = self.config.get("LIMITER_USER_BURST_INTERVAL")

        self.limit_guild_sustain = self.config.get("LIMITER_GUILD_SUSTAIN_TICKETS")
        self.interval_guild_sustain = self.config.get("LIMITER_GUILD_SUSTAIN_INTERVAL")
        self.limit_guild_burst = self.config.get("LIMITER_GUILD_BURST_TICKETS")
        self.interval_guild_burst = self.config.get("LIMITER_GUILD_BURST_INTERVAL")

        self.limit_channel_sustain = self.config.get("LIMITER_CHANNEL_SUSTAIN_TICKETS")
        self.interval_channel_sustain = self.config.get("LIMITER_CHANNEL_SUSTAIN_INTERVAL")
        self.limit_channel_burst = self.config.get("LIMITER_CHANNEL_BURST_TICKETS")
        self.interval_channel_burst = self.config.get("LIMITER_CHANNEL_BURST_INTERVAL")

        # Dictionaries to hold the limiters
        self.servers_sustain = {}
        self.servers_burst = {}
        self.channels_sustain = {}
        self.channels_burst = {}
        self.users_sustain = {}
        self.users_burst = {}

        # The lock is also a synchronous object
        self.lock = asyncio.Lock()
        
        # We add a flag to track if our async setup is complete
        self._async_initialized = False

    # This new method handles all the async setup.
    async def _init_async(self):
        # Prevent this from running more than once
        if self._async_initialized:
            return

        self.limiter_global_sustain = LimitClient(None, self.limit_global_sustain, self.interval_global_sustain,
                                                  "Global (Sustain)", True)
        await self.limiter_global_sustain._init_async()

        self.limiter_global_burst = LimitClient(self.limiter_global_sustain, self.limit_global_burst,
                                                self.interval_global_burst, "Global (Burst)", True)
        await self.limiter_global_burst._init_async()

        self.limiter_dm_sustain = LimitClient(self.limiter_global_burst, self.limit_dm_sustain,
                                              self.interval_dm_sustain, "Global DM (Sustain)", True)
        await self.limiter_dm_sustain._init_async()

        self.limiter_dm_burst = LimitClient(self.limiter_dm_sustain, self.limit_dm_burst, self.interval_dm_burst,
                                            "Global DM (Burst)", True)
        await self.limiter_dm_burst._init_async()
        
        self._async_initialized = True

    # These methods now MUST be async, as they create new LimitClients
    async def get_guild_limiter(self, discord_guild_object: discord.Guild) -> LimitClient:
        limiter_burst = self.servers_burst.get(discord_guild_object.id)
        if not limiter_burst:
            sustain_name = "{} [{}] (Sustain)".format(discord_guild_object.name, discord_guild_object.id)
            burst_name = "{} [{}] (Burst)".format(discord_guild_object.name, discord_guild_object.id)
            
            limiter_sustain = LimitClient(self.limiter_global_burst, self.limit_guild_sustain,
                                          self.interval_guild_sustain, sustain_name)
            await limiter_sustain._init_async()

            limiter_burst = LimitClient(limiter_sustain, self.limit_guild_burst, self.interval_guild_burst, burst_name)
            await limiter_burst._init_async()

            self.servers_sustain[discord_guild_object.id] = limiter_sustain
            self.servers_burst[discord_guild_object.id] = limiter_burst
        return limiter_burst

    async def get_channel_limiter(self, discord_channel_object: discord.TextChannel) -> LimitClient:
        limiter_burst = self.channels_burst.get(discord_channel_object.id)
        if not limiter_burst:
            sustain_name = "{} [{}] (Sustain)".format(discord_channel_object.name, discord_channel_object.id)
            burst_name = "{} [{}] (Burst)".format(discord_channel_object.name, discord_channel_object.id)

            # Note the 'await' here
            parent_limiter = await self.get_guild_limiter(discord_channel_object.guild)
            
            limiter_sustain = LimitClient(parent_limiter,
                                          self.limit_channel_sustain, self.interval_channel_sustain, sustain_name)
            await limiter_sustain._init_async()

            limiter_burst = LimitClient(limiter_sustain, self.limit_channel_burst,
                                        self.interval_channel_burst, burst_name)
            await limiter_burst._init_async()

            self.channels_sustain[discord_channel_object.id] = limiter_sustain
            self.channels_burst[discord_channel_object.id] = limiter_burst
        return limiter_burst

    async def get_user_limiter(self, discord_user_object: discord.User):
        limiter_burst = self.users_burst.get(discord_user_object.id)
        if not limiter_burst:
            sustain_name = "{} [{}] (Sustain)".format(discord_user_object.name, discord_user_object.id)
            burst_name = "{} [{}] (Burst)".format(discord_user_object.name, discord_user_object.id)
            
            limiter_sustain = LimitClient(self.limiter_dm_burst, self.limit_user_sustain, self.interval_user_sustain,
                                          sustain_name)
            await limiter_sustain._init_async()

            limiter_burst = LimitClient(limiter_sustain, self.limit_user_burst, self.interval_user_burst, burst_name)
            await limiter_burst._init_async()

            self.users_sustain[discord_user_object.id] = limiter_sustain
            self.users_burst[discord_user_object.id] = limiter_burst
        return limiter_burst
    
    # This method was already async, we just need to await the new async helpers
    async def get_cm(self, discord_object):
        async with self.lock:
            if isinstance(discord_object, discord.Message):
                if isinstance(discord_object.channel, discord.DMChannel):
                    return await self.get_user_limiter(discord_object.author)
                elif isinstance(discord_object.channel, discord.TextChannel):
                    return await self.get_channel_limiter(discord_object.channel)
                else:
                    traceback.print_stack()
                    raise InsightExc.userInput.InsightProgrammingError("Unknown object type when getting limit manager.")
            elif isinstance(discord_object, discord.TextChannel):
                return await self.get_channel_limiter(discord_object)
            elif isinstance(discord_object, discord.DMChannel):
                return await self.get_user_limiter(discord_object.recipient)
            else:
                print("Unknown object type when getting limit manager. {}".format(type(discord_object)))
                raise InsightExc.userInput.InsightProgrammingError("Unknown object type when getting limit manager.")

    # The rest of the methods are mostly okay, but need loop removal
    def _get_sorted_tickets_consumed(self, limiters_d: dict):
        r = [l for l in limiters_d.values()]
        return sorted(r, key=lambda limiter: limiter.used_tickets(), reverse=True)

    async def _sorted_tickets_consumed(self, limiters_d: dict):
        # Modern way to run in executor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(self._get_sorted_tickets_consumed,
                                                                            limiters_d))

    def get_server_sustained_limiter(self):
        return self.limiter_global_sustain

    async def sorted_servers_consumed(self):
        return await self._sorted_tickets_consumed(self.servers_sustain)

    async def sorted_channels_consumed(self):
        return await self._sorted_tickets_consumed(self.channels_sustain)

    async def sorted_users_consumed(self):
        return await self._sorted_tickets_consumed(self.users_sustain)

    # THIS IS THE NEW WAY TO GET THE SINGLETON INSTANCE
    @classmethod
    async def get_instance(cls):
        """Gets the singleton instance, ensuring it is asynchronously initialized."""
        instance = cls() # This will get the singleton instance
        await instance._init_async() # Ensure it's initialized
        return instance

    # These methods must now use the new get_instance()
    @classmethod
    async def cm(cls, discord_object) -> LimitClient:
        lm = await cls.get_instance()
        return await lm.get_cm(discord_object)

    @classmethod
    async def cm_hp(cls, discord_object) -> LimitClient:
        """"High priority context manager"""
        lm = await cls.get_instance()
        return LimitClientHP(await lm.get_cm(discord_object))