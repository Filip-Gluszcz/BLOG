from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.views.generic import ListView
from .models import Post
from .froms import EmailPostForm, CommentForm, SearchForm
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity

class PostListView(ListView):
    queryset = Post.published.all() # standardowo dodaje sie 'model = Post' ale wtedy widok wywołuje Post.objects.all() zamiast Post.published.all()
    context_object_name = 'posts'
    paginate_by: int = 3
    template_name: str = 'blog/post/list.html'

def post_list(request, tag_slug=None):
    object_list = Post.published.all()
    tag = None

    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        object_list = object_list.filter(tag__in=[tag])
    paginator = Paginator(object_list, 3)
    page = request.GET.get('page')

    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)

    return render(request, 
                    'blog/post/list.html', 
                    {'page': page, 
                    'posts': posts,
                    'tag': tag})

def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post, slug=post, 
                                   status='published', 
                                   publish__year=year, 
                                   publish__month=month, 
                                   publish__day=day)
    
    comments = post.comments.filter(active=True)
    post_tag_ids = post.tag.values_list('id', flat=True) # flat=True powoduje zwrócenie listy wartości zamiast listy krotek wartośći
    similar_posts = Post.published.filter(tag__in=post_tag_ids).exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tag')).order_by('-same_tags', '-publish')[:4]

    if request.method == 'POST':
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            new_comment = comment_form.save(commit=False)
            new_comment.post = post
            new_comment.save()
    else: comment_form = CommentForm()

    return render(request, 
                    'blog/post/detail.html', 
                    {'post': post, 'comments': comments, 
                     'comment_form': comment_form, 
                     'similar_posts': similar_posts})

def post_share(request, post_id):
    post = get_object_or_404(Post, id=post_id, status='published')
    sent = False

    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            email_form_clened_data = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f'{email_form_clened_data["name"]} ({email_form_clened_data["email"]}) zachęca do przeczytania "{post.title}"'
            message = f'Przeczytaj post "{post.title}" na stronie {post_url}\n\n Komentarz dodany przez {email_form_clened_data["name"]}: {email_form_clened_data["comments"]}'
            send_mail(subject, message, 'blog.django.app@gmail.com', [email_form_clened_data['to'],])
            sent = True
    else: 
        form = EmailPostForm()
    return render(request, 'blog/post/share.html', {'post': post, 'form': form, 'sent': sent})

# def post_search(request):
#     form = SearchForm()
#     query = None
#     results = []
#     if 'query' in request.GET:
#         form = SearchForm(request.GET)
#         if form.is_valid():
#             query = form.cleaned_data['query']
#             search_vector = SearchVector('title', weight='A') + SearchVector('body', weight='B')
#             search_query = SearchQuery(query)
#             results = Post.objects.annotate(search=search_vector, rank=SearchRank(search_vector, search_query)).filter(rank__gte=0.3).order_by('-rank')
    
#     return render(request, 'blog/post/search.html', {'form': form, 'results': results, 'query': query})

def post_search(request):
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            results = Post.objects.annotate(similarity=TrigramSimilarity('title', query)).filter(similarity__gte=0.1).order_by('-similarity')
    
    return render(request, 'blog/post/search.html', {'form': form, 'results': results, 'query': query})