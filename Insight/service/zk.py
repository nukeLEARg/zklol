import random
import string
import queue
import datetime
import service
from sqlalchemy.orm import Session
import database.db_tables as dbRow
import statistics
import traceback
import aiohttp
import asyncio
import janus
from functools import partial
from concurrent.futures import ThreadPoolExecutor


class zk(object):
    def __init__(self, service_module):
        assert isinstance(service_module,service.ServiceModule)
        self.service = service_module
        identifier = str(self.generate_identifier())
        self.zk_stream_url = str("https://redisq.zkillboard.com/listen.php?queueID={}".format(identifier))
        self.run = True
        self.error_ids = []
        self.error_ids_last_reset = datetime.datetime.utcnow()
        self.__km_preProcess: janus.Queue = None  # raw json, before insertion to database
        self.__km_postProcess: janus.Queue = None  # fully finished sqlalchemy objects with names resolved
        self.delay_km = queue.Queue()  # delay from occurrence to load
        self.delay_process = queue.Queue()  # process/name resolve delay
        self.delay_next = queue.Queue()  # delay between zk requests
        self.run_websocket = self.service.cli_args.websocket

    @staticmethod
    def add_delay(q, other_time, minutes=False):
        try:
            assert isinstance(q, queue.Queue)
            div_s = 60 if minutes else 1
            q.put_nowait(((datetime.datetime.utcnow() - other_time).total_seconds()) / div_s)
        except Exception as ex:
            print(ex)

    @staticmethod
    def avg_delay(q, median=False):
        assert isinstance(q, queue.Queue)
        values = []
        total = 0
        avg = 0
        try:
            while True:
                values.append(q.get_nowait())
        except queue.Empty:
            try:
                total = len(values)
                if median:
                    avg = statistics.median(values)
                else:
                    avg = sum(values) / total
            except:
                pass
        except Exception as ex:
            print(ex)
        finally:
            return (total, round(avg, 1))

    def get_stats(self):
        _tmp_km_delay = self.avg_delay(self.delay_km, median=True)
        km_delay = (_tmp_km_delay[0], _tmp_km_delay[1] if _tmp_km_delay[1] <= 100 else 99)
        km_process = self.avg_delay(self.delay_process)
        km_next = self.avg_delay(self.delay_next)
        return (km_delay[0], km_delay[1], km_process[1], km_next[1])

    @staticmethod
    def generate_identifier():
        filename = 'zk_identifier.txt'
        try:
            with open(filename, 'r') as f:
                text = f.read()
                return text
        except FileNotFoundError:
            with open(filename, 'w') as f:
                random_s = ''.join(random.choice(string.ascii_lowercase) for x in range(8))
                f.write(random_s)
                return random_s

    def __make_km(self, km_json):
        """returns the cached km object if it does not exist, returns none if error or already exists"""
        result = None
        pull_start_time = datetime.datetime.utcnow()
        try:
            if dbRow.tb_kills.make_row(km_json, self.service) is not None:
                if datetime.datetime.utcnow() >= self.error_ids_last_reset:  # clear error char name ids every hour
                    self.error_ids = []
                    self.error_ids_last_reset = (datetime.datetime.utcnow() + datetime.timedelta(hours=1))
                self.error_ids = dbRow.name_resolver.api_mass_name_resolve(self.service, error_ids=self.error_ids)
                db: Session = self.service.get_session()
                try:
                    result = dbRow.tb_kills.get_row(km_json, self.service)
                    self.add_delay(self.delay_km, result.killmail_time, minutes=True)
                    result.loaded_time = datetime.datetime.utcnow()  # adjust for name resolve
                    self.add_delay(self.delay_process, pull_start_time)
                except Exception as ex:
                    print(ex)
                    traceback.print_exc()
                finally:
                    db.close()
        except Exception as ex:
            print("make_km error: {}".format(ex))
            traceback.print_exc()
        finally:
            return result

    def debug_simulate(self):
        if self.service.cli_args.debug_km:
            msg = "Starting debug mode.\nStarting KM ID: {}\nForce time to now: {}\nKM Limit: {}\n".format(
                str(self.service.cli_args.debug_km), str(self.service.cli_args.force_ctime),
                str(self.service.cli_args.debug_limit))
            print(msg)
            self.service.channel_manager.post_message(msg)
            db: Session = self.service.get_session()
            try:
                results = db.query(dbRow.tb_kills).filter(dbRow.tb_kills.kill_id >=self.service.cli_args.debug_km).limit(self.service.cli_args.debug_limit).all()
                db.close()
                for km in results:
                    if self.service.cli_args.force_ctime:
                        km.killmail_time = datetime.datetime.utcnow()
                    self.__km_postProcess.sync_q.put_nowait(km)
            except Exception as ex:
                print(ex)
            finally:
                db.close()
            msg = "Debugging is now finished. Switching back to streaming live kms."
            print(msg)
            self.service.channel_manager.post_message(msg)

    async def pull_kms_redisq(self):
        """pulls kms using redisq"""
        async with aiohttp.ClientSession(headers=self.service.get_headers()) as client:
            print("Started zk stream (RedisQ/polling) coroutine.")
            next_delay = datetime.datetime.utcnow()
            while self.run:
                try:
                    async with client.get(url=self.zk_stream_url, timeout=45) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            package = data.get('package')
                            if package is not None:
                                await self.__km_preProcess.async_q.put(package)
                            if not self.run_websocket:
                                self.add_delay(self.delay_next, next_delay)
                                next_delay = datetime.datetime.utcnow()
                        elif resp.status == 429:  # error limited
                            print("{} {}".format(str(datetime.datetime.utcnow()),
                                                 "zKill error limited. Are you using more than 1 bot with the same zk queue identifier? Delete your 'zk_identifier.txt' file."))
                            await asyncio.sleep(300)
                        elif 400 <= resp.status < 500:  # calm down zKill is probably overloaded
                            print("{} - RedisQ zk error code: {}".format(str(datetime.datetime.utcnow()), resp.status))
                            await asyncio.sleep(90)
                        elif 500 <= resp.status < 600:
                            print("{} - RedisQ zk error code: {}".format(str(datetime.datetime.utcnow()), resp.status))
                            await asyncio.sleep(60)
                        else:
                            print("{} - RedisQ zk error code: {}".format(str(datetime.datetime.utcnow()), resp.status))
                            await asyncio.sleep(60)
                except asyncio.TimeoutError:
                    await asyncio.sleep(15)
                except Exception as ex:
                    print('ZK RedisQ(polling) error: {}'.format(ex))
                    await asyncio.sleep(30)
                await asyncio.sleep(.1)

    def ws_extract(self, data):
        new_res = {}
        try:
            new_res['killID'] = data['killmail_id']
            new_res['killmail'] = data
            new_res['zkb'] = data['zkb']
        except Exception as ex:
            traceback.print_exc()
            print(ex)
            new_res = {}
        finally:
            return new_res

    async def pull_kms_ws(self):
        if self.run_websocket:
            print("Started zk stream (WebSocket) coroutine.")
            async with aiohttp.ClientSession(headers=self.service.get_headers()) as client:
                while self.run:
                    next_delay = datetime.datetime.utcnow()
                    try:
                        async with client.ws_connect('wss://zkillboard.com:2096', heartbeat=10) as ws:
                            print('{} - ZK WebSocket connection established.'.format(str(datetime.datetime.utcnow())))
                            await ws.send_json(data={"action": "sub", "channel": "killstream"})
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    package = self.ws_extract(msg.json())
                                    if package:
                                        await self.__km_preProcess.async_q.put(package)
                                        self.add_delay(self.delay_next, next_delay)
                                        next_delay = datetime.datetime.utcnow()
                                    else:
                                        print("ZK WebSocket package error.")
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    print("ZK WS error response.")
                                else:
                                    print("ZK WebSocket unknown response.")
                    except Exception as ex:
                        print('{} - ZK WebSocket error: {}'.format(str(datetime.datetime.utcnow()), ex))
                    await asyncio.sleep(25)

    async def coroutine_process_json(self, zk_thread_pool: ThreadPoolExecutor):
        print('Started zk data processing coroutine.')
        loop = asyncio.get_event_loop()
        while True:
            try:
                json_data = await self.__km_preProcess.async_q.get()
                km = await loop.run_in_executor(zk_thread_pool, partial(self.__make_km, json_data))
                if km is not None:
                    await self.__km_postProcess.async_q.put(km)
            except Exception as ex:
                print(ex)

    async def coroutine_filters(self, zk_thread_pool: ThreadPoolExecutor):
        print("Started zk filter coroutine.")
        loop = asyncio.get_event_loop()
        while True:
            try:
                km = await self.__km_postProcess.async_q.get()
                await loop.run_in_executor(zk_thread_pool, partial(self.service.channel_manager.send_km, km))
            except Exception as ex:
                print(ex)

    async def make_queues(self):
        self.__km_preProcess = janus.Queue()
        self.__km_postProcess = janus.Queue()
