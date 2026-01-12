from django.core.management.base import BaseCommand, CommandError
from news_portal.models import Post
from pprint import pprint

class Command(BaseCommand):
    tt = 'Runs'

    def add_arguments(self, parser):
        parser.add_argument('argument', nargs='+', type=int)
    def handle(self,  *args, **options):
        try:
            pk=options['argument'][0]

            post = Post.objects.get(pk=pk)
            self.stdout.write(str(post))
        except:
            raise CommandError('Не найден пост')
        # self.stdout.write(f'options={options}; args={args}; ')
