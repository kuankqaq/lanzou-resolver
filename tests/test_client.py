import unittest
from email.message import Message
from unittest.mock import patch

from lanzou_resolver.client import LanzouClient, LanzouError, compute_acw_sc_v2


class SharePageTests(unittest.TestCase):
    def test_landing_challenge_retries_with_cookie(self):
        headers = Message()
        class Response:
            def geturl(self):
                return 'https://download.example/file/token'
        response = Response()
        response.headers = headers
        arg1 = '0123456789ABCDEF0123456789ABCDEF01234567'
        client = LanzouClient()
        with patch.object(client, '_open', side_effect=[
            (response, f"<script>var arg1='{arg1}';</script>".encode()),
            (response, b'<html>download page</html>'),
        ]) as request:
            _, body = client._open_page(response.geturl(), referer='https://share.example/')
        self.assertEqual(body, b'<html>download page</html>')
        self.assertEqual(request.call_count, 2)
        cookie = next(iter(client.cookies))
        self.assertEqual(cookie.domain, 'download.example')
        self.assertEqual(cookie.value, compute_acw_sc_v2(arg1))
        self.assertEqual(request.call_args.kwargs['referer'], 'https://share.example/')

    def test_inline_sign(self):
        self.assertEqual(
            LanzouClient.parse_share_page(
                "url: '/ajaxm.php?file=123', data: {'sign': 'old-sign'}"
            ),
            ('/ajaxm.php?file=123', 'old-sign'),
        )

    def test_variable_sign_and_comment_decoys(self):
        html = """
        var token = '';
        var token = 'actual-sign';
        // url: '/ajaxm.php?file=999', data: {'sign': 'decoy'}
        /* data: {'sign': 'another-decoy'} */
        $.ajax({url: 'https://apifile.woozooo.com/ajaxfile.php?file=265568085',
                data: {'sign': token}});
        """
        self.assertEqual(
            LanzouClient.parse_share_page(html),
            ('https://apifile.woozooo.com/ajaxfile.php?file=265568085', 'actual-sign'),
        )

    def test_missing_variable(self):
        with self.assertRaises(LanzouError):
            LanzouClient.parse_share_page(
                "url: '/ajaxfile.php?file=123', data: {'sign': missing}"
            )

    def test_password_flow_uses_cross_origin_api(self):
        html = """<input id="pwd">
        var token = 'actual-sign';
        $.ajax({url: 'https://apifile.woozooo.com/ajaxfile.php?file=123',
                data: {'sign': token}});
        """
        headers = Message()
        headers['Content-Type'] = 'application/octet-stream'
        class Response:
            def geturl(self):
                return 'https://download.example/file'
        response = Response()
        response.headers = headers
        client = LanzouClient()
        with patch.object(client, 'get_share_page', return_value=html), patch.object(
            client, '_open', side_effect=[
                (response, b'{"zt":1,"inf":"file.7z","dom":"https://download.example","url":"token"}'),
                (response, b''),
            ]
        ) as request:
            result = client.resolve('https://wwbou.lanzouq.com/example', 'fosv')
        self.assertEqual(result.file_id, '123')
        self.assertEqual(request.call_args_list[0].args[0],
                         'https://apifile.woozooo.com/ajaxfile.php?file=123')
        self.assertEqual(request.call_args_list[0].kwargs['data'], {
            'action': 'downprocess', 'sign': 'actual-sign', 'kd': '1', 'p': 'fosv',
        })


if __name__ == '__main__':
    unittest.main()
