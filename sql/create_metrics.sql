CREATE MATERIALIZED VIEW daily_repo_metrics AS
SELECT 
    CAST(created_at AS DATE) AS creation_date,
    user_type,
    COUNT(DISTINCT user_id) AS total_unique_creators,
    COUNT(id) AS total_repos,
    ROUND(AVG(forks), 2) AS avg_forks,
    ROUND(AVG(size), 2) AS avg_size,
    ROUND(AVG(watchers), 2) AS avg_watchers,
    COUNT(*) FILTER (WHERE language = 'Python') AS python_repos
FROM 
    public.repositories
GROUP BY 
    creation_date, user_type
ORDER BY 
    creation_date, user_type;


CREATE MATERIALIZED VIEW language_summary AS
SELECT language, COUNT(*) AS total_repos, AVG(stargazers_count) AS avg_stars
FROM public.repositories
GROUP BY language
ORDER BY total_repos DESC;


CREATE MATERIALIZED VIEW top_creators AS
SELECT "user", user_type, COUNT(id) AS total_repos, SUM(stargazers_count) AS total_stars
FROM public.repositories
GROUP BY "user", user_type
ORDER BY total_stars DESC
LIMIT 100;