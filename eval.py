import discord
from discord.ext import commands
import io
import textwrap
import traceback
from contextlib import redirect_stdout

# I did not write this file, hence why I seperated it from the main file. I have been using these functions for most of my bots now.

class Eval(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        # remove `foo`
        return content.strip('` \n')

    def get_syntax_error(self, e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    async def to_code_block(self, ctx, body):
        if body.startswith('```') and body.endswith('```'):
            content = '\n'.join(body.split('\n')[1:-1])
        else:
            content = body.strip('`')
            await self.bot.edit_message(ctx.message, '```py\n'+content+'```')

    @commands.command(name='eval')
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):
        '''Run python scripts on discord!'''
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.message.channel,
            'author': ctx.message.author,
            'server': ctx.message.guild,
            'message': ctx.message,
        }
        env.update(globals())
        body = self.cleanup_code(content=body)
        stdout = io.StringIO()
        to_compile = 'async def func():\n%s' % textwrap.indent(body, '  ')
        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await ctx.send(self.get_syntax_error(e))
        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            x = await ctx.send('```py\n{}{}\n```'.format(value, traceback.format_exc()))
            try:
                await x.add_reaction('\U0001f534')
            except:
                pass
        else:
            value = stdout.getvalue() 
        if ret is None:
            if value:
                try:
                    x = await ctx.send('```py\n%s\n```' % value)
                except:
                    x = await ctx.send('```py\n\'Result was too long.\'```')
                try:
                    await x.add_reaction('\U0001f535')
                except:
                    pass
            else:
                try:
                    await ctx.message.add_reaction('\U0001f535')
                except:
                    pass
        else:
            try:
                x = await ctx.send('```py\n%s%s\n```' % (value, ret))
            except:
                x = await ctx.send('```py\n\'Result was too long.\'```')
            try:
                await x.add_reaction('\U0001f535')
            except:
                pass


def setup(bot):
    bot.add_cog(Eval(bot))