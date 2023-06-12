import asyncio
import logging
import os

import argparse
from aiohttp import web
import aiofiles

PHOTO_DIR: str


async def not_found(request):
    async with aiofiles.open('404.html', mode='r') as not_found_page:
        content = await not_found_page.read()
    return web.Response(text=content, content_type='text/html')


async def archive(request):
    *_, requested_dir = request.path.rstrip('/').split('/')
    archive_path = os.path.join(PHOTO_DIR, requested_dir)

    if not os.path.exists(archive_path):
        logging.warning(f'Archive {requested_dir} not found')
        raise web.HTTPFound('/404')

    response = web.StreamResponse()

    response.headers.update({
        'Content-Type': 'multipart/form-data',
        'Content-Disposition': f'filename="{requested_dir}.zip"',
        'Transfer-Encoding': 'chunked',
    })
    response.enable_chunked_encoding()
    await response.prepare(request)
    zipping_process = await asyncio.create_subprocess_exec(
        'zip', '-qr', '-', '.',
        cwd=archive_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        while True:
            chunk = await zipping_process.stdout.read(n=524288)  # 512Kb
            logging.info('Sending archive chunk')
            await response.write(chunk)
            if zipping_process.stdout.at_eof():
                await response.write_eof()
                break
    except (asyncio.CancelledError, IndexError, SystemError, KeyboardInterrupt):
        try:
            await asyncio.wait_for(zipping_process.communicate(b''), timeout=1)
        except TimeoutError:
            zipping_process.kill()
            logging.warning('Download was interrupted')


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r', encoding='utf-8') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main():
    global PHOTO_DIR

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--log_off',
        action='store_false',
        help='Отключить логирование'
    )
    parser.add_argument(
        '--photo_dir',
        default='test_photos',
        help='Задать путь к каталогу с фотографиями'
    )
    parser.add_argument(
        '--log_filename',
        default='server.log',
        help='Задать имя файла логов'
    )
    args = parser.parse_args()

    logging.disable(args.log_off)
    logging.basicConfig(
        level=logging.INFO,
        filename=args.log_filename
    )
    PHOTO_DIR = args.photo_dir

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
        web.get('/404', not_found),
    ])
    web.run_app(
        app,
        host='192.168.0.254',
        port=8080
    )


if __name__ == '__main__':
    main()
