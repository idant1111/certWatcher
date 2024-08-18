import ssl
import socket
from datetime import datetime, timedelta
from OpenSSL import crypto
from urllib.parse import urlparse
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label, Button, Input
from textual.containers import Container, Vertical
from textual.reactive import Reactive
from rich.text import Text
import asyncio

# Set the fetch interval (in seconds)
FETCH_INTERVAL = 360  # 6 minutes for testing purposes
URL_FILE = "urls.txt"

def format_url(url):
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url

def get_certificate_dates(url):
    try:
        url = format_url(url)
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        port = parsed_url.port or 443

        # Get the server certificate in PEM format
        cert_pem = ssl.get_server_certificate((hostname, port))

        # Load the certificate using OpenSSL
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)

        # Extract dates
        issued_date = datetime.strptime(cert.get_notBefore().decode('ascii'), '%Y%m%d%H%M%SZ')
        expiry_date = datetime.strptime(cert.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')

        return issued_date, expiry_date
    except Exception as e:
        return f"Error: {str(e)}", None

def load_urls_from_file(filename=URL_FILE):
    try:
        with open(filename, "r") as file:
            urls = [line.strip() for line in file if line.strip()]
        return urls
    except FileNotFoundError:
        return []

def save_urls_to_file(urls, filename=URL_FILE):
    try:
        with open(filename, "w") as file:
            for url in urls:
                file.write(url + "\n")
    except Exception as e:
        print(f"Error saving URLs: {str(e)}")

def get_status(expiry_date):
    now = datetime.utcnow()
    if expiry_date < now:
        return Text("Expired", style="red")
    elif expiry_date < now + timedelta(weeks=2):
        return Text("About to Expire", style="yellow")
    else:
        return Text("Good", style="green")

class CertCheckerApp(App):
    """A Textual App to check SSL certificate expiry dates and display them in a table."""

    last_fetched: Reactive[str] = Reactive("")
    urls: Reactive[list] = Reactive([])
    def compose(self) -> ComposeResult:
        # Compose the app layout
        yield Header()
        yield Footer()
        yield Container(
            Vertical(
                DataTable(id="table"),
                Label(f"Last fetched: {self.last_fetched}", id="last-fetch-label"),
                Input(placeholder="Enter URL", id="url-input"),
                Button("Add URL", id="add-button"),
                Button("Remove Selected URL", id="remove-button"),
            ),
            id="main-container"
        )

    async def on_mount(self) -> None:
        # Initialize table and label
        self.table = self.query_one(DataTable)
        self.last_fetch_label = self.query_one(Label)
        self.url_input = self.query_one(Input)
        self.urls = load_urls_from_file()

        self.table.add_column("URL", width=40)
        self.table.add_column("Issued On", width=25)
        self.table.add_column("Expires On", width=25)
        self.table.add_column("Status", width=20)

        # Initial fetch
        await self.fetch_and_update()

        # Schedule periodic updates
        asyncio.create_task(self.periodic_fetch())

    async def fetch_and_update(self):
        self.table.clear()  # Clear the table for new data

        if not self.urls:
            self.table.add_row("No URLs found", "-", "-", "-")
        else:
            for url in self.urls:
                issued_date, expiry_date = get_certificate_dates(url)
                if expiry_date:
                    status = get_status(expiry_date)
                    self.table.add_row(url, str(issued_date), str(expiry_date), status)
                else:
                    self.table.add_row(url, "Error", str(issued_date), "Error")

        # Update last fetched time
        self.last_fetched = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_fetch_label.update(f"Last fetched: {self.last_fetched}")

    async def periodic_fetch(self):
        while True:
            await asyncio.sleep(FETCH_INTERVAL)
            await self.fetch_and_update()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-button":
            url = self.url_input.value.strip()
            if url and url not in self.urls:
                self.urls.append(url)
                save_urls_to_file(self.urls)
                await self.fetch_and_update()
                self.url_input.value = ""
        elif event.button.id == "remove-button":
            selected_row = self.table.cursor_row
            if selected_row is not None:
                url_to_remove = self.urls[selected_row]
                self.urls.remove(url_to_remove)
                save_urls_to_file(self.urls)
                await self.fetch_and_update()

if __name__ == "__main__":
    CertCheckerApp().run()
