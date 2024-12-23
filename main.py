import asyncio
import copy
import pickle
from time import time

from tqdm import tqdm

import utils.constants as constants
from service.app import run_service
from updates.fofa import get_channels_by_fofa
from updates.hotel import get_channels_by_hotel
from updates.multicast import get_channels_by_multicast
from updates.online_search import get_channels_by_online_search
from updates.subscribe import get_channels_by_subscribe_urls
from utils.channel import (
    get_channel_items,
    append_total_data,
    process_sort_channel_list,
    write_channel_to_file,
    get_channel_data_cache_with_compare,
    format_channel_url_info,
)
from utils.config import config
from utils.tools import (
    update_file,
    get_pbar_remaining,
    get_ip_address,
    convert_to_m3u,
    process_nested_dict,
    format_interval,
    check_ipv6_support,
    resource_path,
    get_urls_from_file
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

class UpdateSource:
    def __init__(self):
        self.tasks = []
        self.channel_items = {}
        self.channel_data = {}
        self.progress_bar = None
        self.total_urls = 0
        self.start_time = None
        self.results = {}
        self.run_ui = False
        self.update_callback = None

    async def fetch_data(self, channel_names=None):
        """Fetch data using different methods based on configuration."""
        task_configs = [
            ("hotel_fofa", get_channels_by_fofa),
            ("multicast", get_channels_by_multicast),
            ("hotel_foodie", get_channels_by_hotel),
            ("subscribe", self.fetch_subscribe),
            ("online_search", get_channels_by_online_search),
        ]

        tasks = []
        for setting, task_func in task_configs:
            if not config.open_method.get(setting, False):
                continue

            if setting in {"hotel_foodie", "hotel_fofa"} and not config.open_hotel:
                continue

            task = asyncio.create_task(task_func(callback=self.update_progress))
            self.tasks.append(task)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (setting, _), result in zip(task_configs, results):
            if isinstance(result, Exception):
                logging.error(f"Error in {setting}: {result}")
            else:
                self.results[setting] = result

    async def fetch_subscribe(self, callback=None):
        """Fetch subscribe URLs."""
        subscribe_urls = get_urls_from_file(constants.subscribe_path)
        whitelist_urls = get_urls_from_file(constants.whitelist_path)
        return await get_channels_by_subscribe_urls(
            subscribe_urls, whitelist=whitelist_urls, callback=callback
        )

    def update_progress(self, message, progress):
        """Update progress."""
        if self.update_callback:
            self.update_callback(message, progress)

    def setup_progress_bar(self, total, description):
        """Initialize a progress bar."""
        self.progress_bar = tqdm(total=total, desc=description)
        self.start_time = time()

    def update_progress_bar(self, name):
        """Update the progress bar."""
        if self.progress_bar and self.progress_bar.n < self.total_urls:
            self.progress_bar.update()
            remaining = self.total_urls - self.progress_bar.n
            remaining_time = get_pbar_remaining(self.progress_bar.n, self.total_urls, self.start_time)
            self.update_progress(
                f"正在进行{name}, 剩余 {remaining} 个接口, 预计剩余时间: {remaining_time}",
                int((self.progress_bar.n / self.total_urls) * 100),
            )

    async def process_and_sort_data(self):
        """Process and optionally sort the data."""
        if config.open_sort:
            self.total_urls = self.get_urls_length(filter_needed=True)
            self.setup_progress_bar(self.total_urls, "Sorting")
            self.update_progress(f"正在测速排序, 共 {self.total_urls} 个接口需要测速", 0)

            ipv6_support = config.ipv6_support or check_ipv6_support()
            self.channel_data = await process_sort_channel_list(
                self.channel_data, ipv6=ipv6_support, callback=self.update_progress_bar
            )
        else:
            format_channel_url_info(self.channel_data)

    def get_urls_length(self, filter_needed=False):
        """Get the total number of URLs."""
        data = copy.deepcopy(self.channel_data)
        if filter_needed:
            process_nested_dict(data, seen=set(), flag=r"cache:(.*)", force_str="!")
        return sum(
            len(url_info_list)
            for channel_obj in data.values()
            for url_info_list in channel_obj.values()
        )

    async def write_output(self):
        """Write output data to the final file."""
        self.setup_progress_bar(self.get_urls_length(), "Writing")
        ipv6_support = config.ipv6_support or check_ipv6_support()

        write_channel_to_file(
            self.channel_data,
            ipv6=ipv6_support,
            callback=lambda: self.update_progress_bar(name="写入结果"),
        )
        update_file(config.final_file, constants.result_path)

    async def main(self):
        """Main workflow for updating sources."""
        try:
            if config.open_update:
                self.channel_items = get_channel_items()
                channel_names = [
                    name for channel_obj in self.channel_items.values() for name in channel_obj.keys()
                ]
                await self.fetch_data(channel_names)
                append_total_data(
                    self.channel_items.items(),
                    channel_names,
                    self.channel_data,
                    **self.results,
                )
                await self.process_and_sort_data()
                await self.write_output()

            if self.run_ui:
                url = get_ip_address() if config.open_service else None
                tip = f"✅ 更新完成，请检查 {config.final_file} 文件。"
                self.update_progress(tip, 100, url=url)
                if config.open_service:
                    run_service()

        except asyncio.exceptions.CancelledError:
            logging.warning("Update process was cancelled!")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    async def start(self, callback=None):
        """Start the update process."""
        self.update_callback = callback
        self.run_ui = callback is not None
        await self.main()

    def stop(self):
        """Stop the update process."""
        for task in self.tasks:
            task.cancel()
        if self.progress_bar:
            self.progress_bar.close()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update_source = UpdateSource()
    loop.run_until_complete(update_source.start())
