import discord
import random
import json
import os
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

statuses = [
    "Doing Orders...",
    "Coded By frkxs",
    "Fixing My Code",
    "Listening To Ken Carson",
    "Doing Tickets...",
    "Making Accounts"
]

TICKET_DATA_FILE = "tickets.json"

def load_tickets():
    if os.path.exists(TICKET_DATA_FILE):
        with open(TICKET_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_ticket(ticket_id, channel_id):
    tickets = load_tickets()
    tickets[ticket_id] = channel_id
    with open(TICKET_DATA_FILE, "w") as f:
        json.dump(tickets, f)

def get_ticket_channel(ticket_id):
    tickets = load_tickets()
    return tickets.get(ticket_id)

@tasks.loop(seconds=2)
async def change_status():
    await bot.change_presence(activity=discord.Game(random.choice(statuses)))

@bot.event
async def on_ready():
    change_status.start()
    print(f'Bot is ready. Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(e)
    # Restore tickets
    tickets = load_tickets()
    guild = discord.utils.get(bot.guilds)  # Assuming a single guild, modify if you have multiple
    for ticket_id, channel_id in tickets.items():
        channel = guild.get_channel(channel_id)
        if channel:
            view = TicketActionsView(ticket_id)
            bot.add_view(view, message_id=channel.last_message_id)  # assuming the last message is the ticket message

class TicketActionsView(View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.add_item(Button(label="Claim", style=discord.ButtonStyle.green, custom_id=f"claim_ticket_{ticket_id}"))
        self.add_item(Button(label="Close", style=discord.ButtonStyle.red, custom_id=f"close_ticket_{ticket_id}"))
        self.add_item(Button(label="Delete", style=discord.ButtonStyle.gray, custom_id=f"delete_ticket_{ticket_id}"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green)
    async def claim_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role = discord.utils.get(interaction.guild.roles, name="Support Member")
        claimed_by = interaction.user
        overwrites = interaction.channel.overwrites
        overwrites[claimed_by] = discord.PermissionOverwrite(read_messages=True)
        overwrites[support_role] = discord.PermissionOverwrite(read_messages=False)
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.response.send_message(f"Ticket claimed by {claimed_by.mention}", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red)
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        overwrites = interaction.channel.overwrites
        for target in overwrites:
            overwrites[target].send_messages = False
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.response.send_message("Ticket closed successfully!", ephemeral=True)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.gray)
    async def delete_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = interaction.channel.id
        await interaction.channel.delete()
        await interaction.response.send_message("Ticket deleted successfully!", ephemeral=True)
        # Remove the ticket from the stored data
        tickets = load_tickets()
        for ticket_id, cid in tickets.items():
            if cid == channel_id:
                del tickets[ticket_id]
                break
        with open(TICKET_DATA_FILE, "w") as f:
            json.dump(tickets, f)

class BuyServiceView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("What is your form of payment?", view=PaymentView(), ephemeral=True)

class PaymentView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Crypto", style=discord.ButtonStyle.blurple, custom_id="payment_crypto")
    async def payment_crypto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_service(interaction, "Crypto")

    @discord.ui.button(label="Apple Pay", style=discord.ButtonStyle.blurple, custom_id="payment_apple_pay")
    async def payment_apple_pay(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_service(interaction, "Apple Pay")

    @discord.ui.button(label="Cash App", style=discord.ButtonStyle.blurple, custom_id="payment_cash_app")
    async def payment_cash_app(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_service(interaction, "Cash App")

    @discord.ui.button(label="PayPal", style=discord.ButtonStyle.blurple, custom_id="payment_paypal")
    async def payment_paypal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_service(interaction, "PayPal")

    async def prompt_service(self, interaction: discord.Interaction, payment_method: str):
        modal = ServiceModal(payment_method)
        await interaction.response.send_modal(modal)

class ServiceModal(Modal):
    def __init__(self, payment_method: str):
        super().__init__(title="Service Information")
        self.payment_method = payment_method
        self.add_item(TextInput(label="Service", placeholder="Enter the service you want", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        service = self.children[0].value
        guild = interaction.guild
        support_role = discord.utils.get(guild.roles, name="Support Member")
        random_number = random.randint(1000, 9999)
        ticket_id = f"{interaction.user.id}_{random_number}"
        ticket_channel_name = f"ticket-{service}-{interaction.user.name}-{random_number}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True),
            support_role: discord.PermissionOverwrite(read_messages=True)
        }
        ticket_channel = await guild.create_text_channel(ticket_channel_name, overwrites=overwrites)
        embed = discord.Embed(title="Support Ticket", description=f"Support will be with you shortly, {interaction.user.mention}. You have selected **{service}**. Payment method: **{self.payment_method}**.", color=0x00ff00)
        view = TicketActionsView(ticket_id)
        msg = await ticket_channel.send(content=support_role.mention, embed=embed, view=view)
        await interaction.response.send_message("Ticket created successfully!", ephemeral=True)
        save_ticket(ticket_id, ticket_channel.id)

@bot.tree.command(name="payments", description="Show payment options")
async def payments(interaction: discord.Interaction):
    crypto_emoji = '<:Crypto:1251165660848066732>'
    apple_pay_emoji = '<:applepay:1251165789248032768>'
    cash_app_emoji = '<:cashapp:1251165591608496158>'
    paypal_emoji = '<:paypal:1251165514202480702>'
    embed = discord.Embed(title="Payment Options", description="Choose one of the payment methods below:", color=0x00ff00)
    
    embed.add_field(name=f"{crypto_emoji} Crypto", value="Not Available at the moment", inline=False)
    embed.add_field(name=f"{apple_pay_emoji} Apple Pay", value="Available", inline=False)
    embed.add_field(name=f"{cash_app_emoji} Cash App", value="$darephantom", inline=False)
    embed.add_field(name=f"{paypal_emoji} PayPal", value="MaximGinga", inline=False)
    
    embed.set_footer(text="MagicShop Services")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ticket", description="Buy Service")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title="Buy Service", description="Click the button below to create a ticket.", color=0x00ff00)
    await interaction.response.send_message(embed=embed, view=BuyServiceView())

bot.run('MTI1MTIwMjE5NzM2NzE2NTA2MQ.GgeTZk.xQklaST0QRggQ4GpHZBb5J_TEZ5ESG9Le-0EVQ')