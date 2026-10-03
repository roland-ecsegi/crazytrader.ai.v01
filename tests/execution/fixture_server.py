"""Disposable authoritative fixture on actual PostgreSQL; not an exchange simulator."""

import hashlib
import hmac
import json
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


@contextmanager
def sdk_venue(
    store,
    tenant,
    timeout_after_accept=True,
    timeout_after_cancel=False,
    account_history_unavailable=False,
    authoritative_not_found=False,
):
    with store.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ct_test_wire_orders (tenant text NOT NULL, "
            "client_id text NOT NULL, body text NOT NULL, PRIMARY KEY(tenant,client_id))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ct_test_wire_posts "
            "(tenant text NOT NULL, client_id text NOT NULL)"
        )

    with store.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ct_test_wire_fills "
            "(tenant text NOT NULL, trade_id bigint NOT NULL, body text NOT NULL, "
            "PRIMARY KEY(tenant,trade_id))"
        )

    with store.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ct_test_wire_cancels "
            "(tenant text NOT NULL, client_id text NOT NULL)"
        )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # no request signatures/auth/query in ordinary logs

        def params(self):
            encoded = urlsplit(self.path).query
            params = parse_qs(encoded)
            length = int(self.headers.get("Content-Length", "0"))
            if length:
                body = self.rfile.read(length).decode()
                encoded = encoded + ("&" if encoded else "") + body
                params.update(parse_qs(body))
            unsigned = "&".join(
                part for part in encoded.split("&") if not part.startswith("signature=")
            )
            signature = hmac.new(b"fixture", unsigned.encode(), hashlib.sha256).hexdigest()
            assert self.headers["X-MBX-APIKEY"] == "fixture-only-key"
            assert hmac.compare_digest(params["signature"][0], signature)
            return {key: values[0] for key, values in params.items()}

        def respond(self, body, status=200):
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            assert urlsplit(self.path).path == "/api/v3/order"
            assert self.headers["X-MBX-APIKEY"] == "fixture-only-key"
            params = self.params()
            assert params["signature"]
            client_id = params["newClientOrderId"]
            body = {
                "symbol": params["symbol"],
                "orderId": 101,
                "orderListId": -1,
                "clientOrderId": client_id,
                "transactTime": 1790985600000,
                "price": "0",
                "origQty": params["quantity"],
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "status": "NEW",
                "timeInForce": "GTC",
                "type": params["type"],
                "side": params["side"],
                "fills": [],
                "workingTime": 1790985600000,
                "selfTradePreventionMode": "NONE",
            }
            # Actual venue-side commit happens before timeout. New server instance
            # after application/fixture restart queries the same authoritative row.
            with store.connection() as conn:
                conn.execute(
                    "INSERT INTO ct_test_wire_posts(tenant,client_id) VALUES(%s,%s)",
                    (tenant, client_id),
                )
                conn.execute(
                    "INSERT INTO ct_test_wire_orders(tenant,client_id,body) "
                    "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                    (tenant, client_id, json.dumps(body)),
                )
            if timeout_after_accept:
                time.sleep(0.35)  # SDK request timeout150ms, no retry allowed
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
            else:
                self.respond(body)

        def do_DELETE(self):
            assert urlsplit(self.path).path == "/api/v3/order"
            params = self.params()
            client_id = params["origClientOrderId"]
            with store.connection() as conn:
                conn.execute(
                    "INSERT INTO ct_test_wire_cancels(tenant,client_id) VALUES(%s,%s)",
                    (tenant, client_id),
                )
                row = conn.execute(
                    "SELECT body FROM ct_test_wire_orders WHERE tenant=%s AND client_id=%s",
                    (tenant, client_id),
                ).fetchone()
                if row is None or json.loads(row["body"])["status"] == "FILLED":
                    self.send_response(400)
                    self.end_headers()
                    return
                body = json.loads(row["body"])
                body.update(status="CANCELED", origClientOrderId=client_id)
                conn.execute(
                    "UPDATE ct_test_wire_orders SET body=%s WHERE tenant=%s AND client_id=%s",
                    (json.dumps(body), tenant, client_id),
                )
            if timeout_after_cancel:
                time.sleep(0.35)
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
            else:
                self.respond(body)

        def do_GET(self):
            params = self.params()
            path = urlsplit(self.path).path
            if path == "/api/v3/account":
                with store.connection() as conn:
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS ct_test_wire_accounts (tenant text PRIMARY "
                        "KEY, body text NOT NULL)"
                    )
                    row = conn.execute(
                        "SELECT body FROM ct_test_wire_accounts WHERE tenant=%s", (tenant,)
                    ).fetchone()
                body = (
                    json.loads(row["body"])
                    if row
                    else {
                        "makerCommission": 0,
                        "takerCommission": 0,
                        "buyerCommission": 0,
                        "sellerCommission": 0,
                        "commissionRates": {
                            "maker": "0",
                            "taker": "0",
                            "buyer": "0",
                            "seller": "0",
                        },
                        "canTrade": True,
                        "canWithdraw": False,
                        "canDeposit": False,
                        "brokered": False,
                        "requireSelfTradePrevention": False,
                        "preventSor": False,
                        "updateTime": 1790985600000,
                        "accountType": "SPOT",
                        "permissions": ["SPOT"],
                        "uid": 1,
                        "balances": [
                            {"asset": "BTC", "free": "1", "locked": "0"},
                            {"asset": "USDT", "free": "0", "locked": "0"},
                        ],
                    }
                )
                self.respond(body)
                return
            if path in {"/api/v3/openOrders", "/api/v3/allOrders"}:
                if account_history_unavailable and path == "/api/v3/allOrders":
                    self.send_response(503)
                    self.end_headers()
                    return
                with store.connection() as conn:
                    rows = conn.execute(
                        "SELECT body FROM ct_test_wire_orders WHERE tenant=%s", (tenant,)
                    ).fetchall()
                bodies = [json.loads(row["body"]) for row in rows]
                if path.endswith("openOrders"):
                    bodies = [b for b in bodies if b["status"] in {"NEW", "PARTIALLY_FILLED"}]
                else:
                    bodies = [
                        b
                        for b in bodies
                        if b["symbol"] == params["symbol"]
                        and b["orderId"] >= int(params.get("orderId", "0"))
                    ]
                bodies.sort(key=lambda b: b["orderId"])
                for body in bodies:
                    body.update(
                        time=1790985600000,
                        updateTime=1790985600000,
                        isWorking=True,
                        origQuoteOrderQty="0",
                        icebergQty="0",
                        stopPrice="0",
                    )
                self.respond(bodies[: int(params.get("limit", "1000"))])
                return
            if urlsplit(self.path).path == "/api/v3/myTrades":
                assert params["signature"]
                with store.connection() as conn:
                    if "orderId" in params:
                        rows = conn.execute(
                            "SELECT body FROM ct_test_wire_fills WHERE tenant=%s "
                            "AND body::jsonb->>'orderId'=%s ORDER BY trade_id",
                            (tenant, params["orderId"]),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT body FROM ct_test_wire_fills WHERE tenant=%s "
                            "AND body::jsonb->>'symbol'=%s AND trade_id>=%s ORDER BY trade_id "
                            "LIMIT 1000",
                            (tenant, params["symbol"], int(params.get("fromId", "0"))),
                        ).fetchall()
                self.respond([json.loads(row["body"]) for row in rows])
                return
            assert urlsplit(self.path).path == "/api/v3/order"
            assert params["signature"]
            with store.connection() as conn:
                row = conn.execute(
                    "SELECT body FROM ct_test_wire_orders WHERE tenant=%s AND client_id=%s",
                    (tenant, params["origClientOrderId"]),
                ).fetchone()
            if row is None:
                if authoritative_not_found:
                    self.respond({"code": -2013, "msg": "Order does not exist."}, status=400)
                else:
                    self.send_response(400)
                    self.end_headers()
                return
            body = json.loads(row["body"])
            body.update(
                time=1790985600000,
                updateTime=1790985600000,
                isWorking=True,
                origQuoteOrderQty="0",
                icebergQty="0",
                stopPrice="0",
            )
            self.respond(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
