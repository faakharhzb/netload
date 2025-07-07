import sys
from http.client import HTTPConnection, HTTPSConnection, HTTPResponse
from urllib.parse import urlparse, ParseResult
from time import perf_counter
from itertools import cycle
from threading import Thread
from mimetypes import guess_extension


def parse_url(raw_url: str) -> ParseResult:
    if not raw_url.startswith(('https://', 'http://')):
        print(f'prepended {"https://"} to {raw_url}')
        raw_url = 'https://' + raw_url

    url = urlparse(raw_url)
    return url


def make_conn(url: ParseResult) -> HTTPConnection | HTTPSConnection:
    if url.scheme == 'https':
        conn = HTTPSConnection(url.netloc)
    elif url.scheme == 'http':
        conn = HTTPConnection(url.netloc)
    else:
        print('Unsupported URL scheme: ', url.scheme)
        sys.exit(1)

    print('Connected with', url.netloc)
    return conn


def get_response(
    conn: HTTPConnection | HTTPSConnection, url: ParseResult
) -> HTTPResponse:
    print('Fetching response...', end=' ')

    if url.query:
        path = url.path + '?' + url.query
    else:
        path = url.path

    conn.request('GET', path if path else '/')
    response = conn.getresponse()
    print(response.status, response.reason)

    return response


def manage_response_status(response: HTTPResponse) -> None | str:
    if response.status in (301, 302, 303, 307, 308):
        location = response.getheader('Location')
        print('Redirecting to:', location)
        return location
    elif response.status == 404:
        print('URL Not Found')
        sys.exit(1)
    elif response.status != 200:
        print(f'Failed: {response.status} {response.reason}')
        sys.exit(1)
    else:
        return None


def fetch_data(
    raw_url: str, redirect_limit: int = 5
) -> tuple[ParseResult, HTTPResponse]:
    for _ in range(redirect_limit):
        url = parse_url(raw_url)

        conn = make_conn(url)
        response = get_response(conn, url)

        raw_url = manage_response_status(response)
        if not raw_url:
            return (url, response)

    print('Too many redirects.')
    sys.exit(1)


def save_file(
    response: HTTPResponse,
    filename: str,
    size: int,
    chunk_size: int,
) -> None:
    downloaded = 0

    wheel = cycle(['|', '/', '—', '\\', '—'])

    print('Downloading file...')

    with open(filename, 'wb') as f:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break

            downloaded += len(chunk)

            f.write(chunk)

            if type(size) is int:
                progress = int(50 * downloaded // size)
                percent = str(100 * downloaded // size)
                percent += '%' + ' ' * (3 - len(percent))

                bar = '[' + '#' * progress + ' ' * (50 - progress) + ']'

                print(f'\r{percent} {bar}  {downloaded} B', end='')
            else:
                print(f'\r{next(wheel)}, {downloaded} B', end='')


def set_file_path(response: HTTPResponse, url: ParseResult) -> tuple[str, str]:
    filetype = guess_extension(response.getheader('Content-Type').split(';')[0])

    if '-o' in sys.argv:
        file_path = sys.argv[sys.argv.index('-o') + 1]
    elif '--output' in sys.argv:
        file_path = sys.argv[sys.argv.index('--output') + 1]
    else:
        file_path = url.path.split('/')[-1] or f'index.{filetype}'
        if not file_path.endswith(filetype):
            file_path += '.' + filetype

    return (file_path, filetype)


def manage_sizes(response: HTTPResponse) -> tuple[int | str, str, int]:
    size = response.getheader('Content-Length')

    if size:
        size = int(size)

        if size >= 1024 and size < 1024**2:
            formatted_size = f'{size / 1024:.1f}' + ' KB'
        elif size >= 1024**2:
            formatted_size = f'{size / (1024**2):.1f}' + ' MB'
        else:
            formatted_size = f'{size:.1f}' + ' B'

        if size > 1024**2:
            chunk = 1024 * 16
        else:
            chunk = 4096
    else:
        size = 'Unknown'
        formatted_size = 'Unknown'

        chunk = 4096

    return (size, formatted_size, chunk)


def main(raw_url: str) -> None:
    start = perf_counter()

    url, response = fetch_data(raw_url)

    file_path, filetype = set_file_path(response, url)

    size, formatted_size, chunk = manage_sizes(response)

    print(f'File size: {formatted_size}')

    save_file(response, file_path, size, chunk)

    print(f'  {perf_counter() - start:.2f} Seconds')
    print(f"\nFile '{file_path}' saved.")


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except IndexError:
        sys.exit()
