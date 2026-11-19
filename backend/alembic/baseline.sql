CREATE TABLE [dbo].[admin_audit_logs] (
    [id] int IDENTITY(1,1) NOT NULL,
    [admin_user_id] uniqueidentifier NOT NULL,
    [action_type] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [target_type] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [target_id] varchar(100) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [notes] varchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__admin_aud__creat__522F1F86] DEFAULT (getdate()),
    CONSTRAINT [PK__admin_au__3213E83FBEEBB385] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[auth_sessions] (
    [id] uniqueidentifier NOT NULL CONSTRAINT [DF__auth_session__id__55FFB06A] DEFAULT (newsequentialid()),
    [user_id] uniqueidentifier NOT NULL,
    [refresh_token] varchar(512) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [ip_address] varchar(100) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [user_agent] varchar(500) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [expires_at] datetime NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__auth_sess__creat__56F3D4A3] DEFAULT (getdate()),
    CONSTRAINT [PK__auth_ses__3213E83FC014F421] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[bookmarks] (
    [user_id] uniqueidentifier NOT NULL,
    [post_id] int NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__bookmarks__creat__6FBF826D] DEFAULT (getdate()),
    CONSTRAINT [PK__bookmark__CA534F793CC48DE1] PRIMARY KEY CLUSTERED ([user_id] ASC, [post_id] ASC)
)
GO

CREATE TABLE [dbo].[comments] (
    [id] int IDENTITY(1,1) NOT NULL,
    [post_id] int NOT NULL,
    [user_id] uniqueidentifier NOT NULL,
    [parent_id] int NULL,
    [content] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__comments__create__7484378A] DEFAULT (getdate()),
    [status] varchar(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT [DF_comments_status] DEFAULT ('active'),
    CONSTRAINT [PK__comments__3213E83FB00B3EA4] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[email_verification_tokens] (
    [id] uniqueidentifier NOT NULL CONSTRAINT [DF__email_verifi__id__5AC46587] DEFAULT (newsequentialid()),
    [user_id] uniqueidentifier NOT NULL,
    [token] varchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [expires_at] datetime NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__email_ver__creat__5BB889C0] DEFAULT (getdate()),
    CONSTRAINT [PK__email_ve__3213E83F66C4522B] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[follows] (
    [follower_id] uniqueidentifier NOT NULL,
    [following_id] uniqueidentifier NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__follows__created__5F891AA4] DEFAULT (getdate()),
    CONSTRAINT [PK__follows__CAC186A7E9FA2DD8] PRIMARY KEY CLUSTERED ([follower_id] ASC, [following_id] ASC)
)
GO

CREATE TABLE [dbo].[notifications] (
    [id] int IDENTITY(1,1) NOT NULL,
    [user_id] uniqueidentifier NOT NULL,
    [actor_id] uniqueidentifier NULL,
    [type] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [title] varchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [message] varchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [is_read] bit NOT NULL CONSTRAINT [DF__notificat__is_re__13FCE2E3] DEFAULT ('0'),
    [post_id] int NULL,
    [comment_id] int NULL,
    [report_id] int NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__notificat__creat__14F1071C] DEFAULT (getdate()),
    CONSTRAINT [PK__notifica__3213E83F704F8DCA] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[password_reset_tokens] (
    [id] uniqueidentifier NOT NULL CONSTRAINT [DF__password_res__id__6AFACD50] DEFAULT (newsequentialid()),
    [user_id] uniqueidentifier NOT NULL,
    [token] varchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [expires_at] datetime NOT NULL,
    [used_at] datetime NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__password___creat__6BEEF189] DEFAULT (getdate()),
    CONSTRAINT [PK__password__3213E83F0DD7D3EF] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[post_likes] (
    [user_id] uniqueidentifier NOT NULL,
    [post_id] int NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__post_like__creat__7A3D10E0] DEFAULT (getdate()),
    CONSTRAINT [PK__post_lik__CA534F79F86E1DB2] PRIMARY KEY CLUSTERED ([user_id] ASC, [post_id] ASC)
)
GO

CREATE TABLE [dbo].[post_shares] (
    [id] int IDENTITY(1,1) NOT NULL,
    [post_id] int NOT NULL,
    [user_id] uniqueidentifier NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__post_shar__creat__7F01C5FD] DEFAULT (getdate()),
    CONSTRAINT [PK__post_sha__3213E83F4269023F] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[post_tags] (
    [post_id] int NOT NULL,
    [tag_id] int NOT NULL,
    CONSTRAINT [PK__post_tag__4AFEED4D73A2F6FA] PRIMARY KEY CLUSTERED ([post_id] ASC, [tag_id] ASC)
)
GO

CREATE TABLE [dbo].[post_views] (
    [id] int IDENTITY(1,1) NOT NULL,
    [post_id] int NOT NULL,
    [user_id] uniqueidentifier NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__post_view__creat__07970BFE] DEFAULT (getdate()),
    CONSTRAINT [PK__post_vie__3213E83F17A94CDB] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[posts] (
    [id] int IDENTITY(1,1) NOT NULL,
    [user_id] uniqueidentifier NOT NULL,
    [title] nvarchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [slug] varchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [content] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [cover_image] varchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [status] varchar(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT [DF__posts__status__6541F3FA] DEFAULT ('pending'),
    [original_post_id] int NULL,
    [share_caption] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [requested_new_tags] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__posts__created_a__66361833] DEFAULT (getdate()),
    CONSTRAINT [PK__posts__3213E83F3AE18C29] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__posts__32DD1E4C258C5A89] UNIQUE NONCLUSTERED ([slug] ASC)
)
GO

CREATE TABLE [dbo].[reports] (
    [id] int IDENTITY(1,1) NOT NULL,
    [reporter_id] uniqueidentifier NULL,
    [post_id] int NULL,
    [comment_id] int NULL,
    [reason] varchar(100) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [details] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [status] varchar(30) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT [DF__reports__status__0C5BC11B] DEFAULT ('pending'),
    [reviewed_by] uniqueidentifier NULL,
    [reviewed_at] datetime NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__reports__created__0D4FE554] DEFAULT (getdate()),
    CONSTRAINT [PK__reports__3213E83FA9815912] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[tags] (
    [id] int IDENTITY(1,1) NOT NULL,
    [name] varchar(100) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [slug] varchar(120) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [created_at] datetime NOT NULL CONSTRAINT [DF__tags__created_at__47B19113] DEFAULT (getdate()),
    CONSTRAINT [PK__tags__3213E83FCB5F4B44] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

CREATE TABLE [dbo].[users] (
    [id] uniqueidentifier NOT NULL CONSTRAINT [DF__users__id__4A8DFDBE] DEFAULT (newsequentialid()),
    [username] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [email] varchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [password_hash] varchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [full_name] nvarchar(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    [avatar_url] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [bio] nvarchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [major] nvarchar(120) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [academic_year] varchar(30) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [career_goal] nvarchar(200) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [interest_tags] varchar(MAX) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
    [role] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT [DF__users__role__4B8221F7] DEFAULT ('Student'),
    [status] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT [DF__users__status__4C764630] DEFAULT ('active'),
    [provider] varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT [DF__users__provider__4D6A6A69] DEFAULT ('local'),
    [is_verified] bit NOT NULL CONSTRAINT [DF__users__is_verifi__4E5E8EA2] DEFAULT ('0'),
    [created_at] datetime NOT NULL CONSTRAINT [DF__users__created_a__4F52B2DB] DEFAULT (getdate()),
    CONSTRAINT [PK__users__3213E83F203CA9A5] PRIMARY KEY CLUSTERED ([id] ASC)
)
GO

ALTER TABLE [dbo].[admin_audit_logs] WITH CHECK ADD CONSTRAINT [FK__admin_aud__admin__532343BF] FOREIGN KEY ([admin_user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_admin_audit_logs_action_type] ON [dbo].[admin_audit_logs] ([action_type] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_admin_audit_logs_admin_user_id] ON [dbo].[admin_audit_logs] ([admin_user_id] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_admin_audit_logs_created_at] ON [dbo].[admin_audit_logs] ([created_at] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_admin_audit_logs_target_type] ON [dbo].[admin_audit_logs] ([target_type] ASC)
GO

ALTER TABLE [dbo].[auth_sessions] WITH CHECK ADD CONSTRAINT [FK__auth_sess__user___57E7F8DC] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE CASCADE ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_auth_sessions_id] ON [dbo].[auth_sessions] ([id] ASC)
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_auth_sessions_refresh_token] ON [dbo].[auth_sessions] ([refresh_token] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_auth_sessions_user_id] ON [dbo].[auth_sessions] ([user_id] ASC)
GO

ALTER TABLE [dbo].[bookmarks] WITH CHECK ADD CONSTRAINT [FK__bookmarks__post___71A7CADF] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[bookmarks] WITH CHECK ADD CONSTRAINT [FK__bookmarks__user___70B3A6A6] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[comments] WITH CHECK ADD CONSTRAINT [FK__comments__parent__7760A435] FOREIGN KEY ([parent_id]) REFERENCES [dbo].[comments] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[comments] WITH CHECK ADD CONSTRAINT [FK__comments__post_i__75785BC3] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[comments] WITH CHECK ADD CONSTRAINT [FK__comments__user_i__766C7FFC] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_comments_post_id] ON [dbo].[comments] ([post_id] ASC)
GO

CREATE NONCLUSTERED INDEX [IX_comments_status] ON [dbo].[comments] ([status] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_comments_user_id] ON [dbo].[comments] ([user_id] ASC)
GO

ALTER TABLE [dbo].[email_verification_tokens] WITH CHECK ADD CONSTRAINT [FK__email_ver__user___5CACADF9] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_email_verification_tokens_token] ON [dbo].[email_verification_tokens] ([token] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_email_verification_tokens_user_id] ON [dbo].[email_verification_tokens] ([user_id] ASC)
GO

ALTER TABLE [dbo].[follows] WITH CHECK ADD CONSTRAINT [FK__follows__followe__607D3EDD] FOREIGN KEY ([follower_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[follows] WITH CHECK ADD CONSTRAINT [FK__follows__followi__61716316] FOREIGN KEY ([following_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[notifications] WITH CHECK ADD CONSTRAINT [FK__notificat__actor__16D94F8E] FOREIGN KEY ([actor_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[notifications] WITH CHECK ADD CONSTRAINT [FK__notificat__comme__18C19800] FOREIGN KEY ([comment_id]) REFERENCES [dbo].[comments] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[notifications] WITH CHECK ADD CONSTRAINT [FK__notificat__post___17CD73C7] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[notifications] WITH CHECK ADD CONSTRAINT [FK__notificat__repor__19B5BC39] FOREIGN KEY ([report_id]) REFERENCES [dbo].[reports] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[notifications] WITH CHECK ADD CONSTRAINT [FK__notificat__user___15E52B55] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_notifications_user_id] ON [dbo].[notifications] ([user_id] ASC)
GO

ALTER TABLE [dbo].[password_reset_tokens] WITH CHECK ADD CONSTRAINT [FK__password___user___6CE315C2] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE CASCADE ON UPDATE NO ACTION
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_password_reset_tokens_token] ON [dbo].[password_reset_tokens] ([token] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_password_reset_tokens_user_id] ON [dbo].[password_reset_tokens] ([user_id] ASC)
GO

ALTER TABLE [dbo].[post_likes] WITH CHECK ADD CONSTRAINT [FK__post_like__post___7C255952] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[post_likes] WITH CHECK ADD CONSTRAINT [FK__post_like__user___7B313519] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[post_shares] WITH CHECK ADD CONSTRAINT [FK__post_shar__post___7FF5EA36] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[post_shares] WITH CHECK ADD CONSTRAINT [FK__post_shar__user___00EA0E6F] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_post_shares_post_id] ON [dbo].[post_shares] ([post_id] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_post_shares_user_id] ON [dbo].[post_shares] ([user_id] ASC)
GO

ALTER TABLE [dbo].[post_tags] WITH CHECK ADD CONSTRAINT [FK__post_tags__post___03C67B1A] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE CASCADE ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[post_tags] WITH CHECK ADD CONSTRAINT [FK__post_tags__tag_i__04BA9F53] FOREIGN KEY ([tag_id]) REFERENCES [dbo].[tags] ([id]) ON DELETE CASCADE ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[post_views] WITH CHECK ADD CONSTRAINT [FK__post_view__post___088B3037] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[post_views] WITH CHECK ADD CONSTRAINT [FK__post_view__user___097F5470] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_post_views_post_id] ON [dbo].[post_views] ([post_id] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_post_views_user_id] ON [dbo].[post_views] ([user_id] ASC)
GO

ALTER TABLE [dbo].[posts] WITH CHECK ADD CONSTRAINT [FK__posts__original___681E60A5] FOREIGN KEY ([original_post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[posts] WITH CHECK ADD CONSTRAINT [FK__posts__user_id__672A3C6C] FOREIGN KEY ([user_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[posts] WITH CHECK ADD CONSTRAINT [FK_posts_original_post_id] FOREIGN KEY ([original_post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_posts_original_post_id] ON [dbo].[posts] ([original_post_id] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_posts_status] ON [dbo].[posts] ([status] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_posts_user_id] ON [dbo].[posts] ([user_id] ASC)
GO

ALTER TABLE [dbo].[reports] WITH CHECK ADD CONSTRAINT [FK__reports__comment__102C51FF] FOREIGN KEY ([comment_id]) REFERENCES [dbo].[comments] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[reports] WITH CHECK ADD CONSTRAINT [FK__reports__post_id__0F382DC6] FOREIGN KEY ([post_id]) REFERENCES [dbo].[posts] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[reports] WITH CHECK ADD CONSTRAINT [FK__reports__reporte__0E44098D] FOREIGN KEY ([reporter_id]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

ALTER TABLE [dbo].[reports] WITH CHECK ADD CONSTRAINT [FK__reports__reviewe__11207638] FOREIGN KEY ([reviewed_by]) REFERENCES [dbo].[users] ([id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

CREATE NONCLUSTERED INDEX [ix_reports_comment_id] ON [dbo].[reports] ([comment_id] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_reports_post_id] ON [dbo].[reports] ([post_id] ASC)
GO

CREATE NONCLUSTERED INDEX [ix_reports_reporter_id] ON [dbo].[reports] ([reporter_id] ASC)
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_tags_name] ON [dbo].[tags] ([name] ASC)
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_tags_slug] ON [dbo].[tags] ([slug] ASC)
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_users_email] ON [dbo].[users] ([email] ASC)
GO

CREATE UNIQUE NONCLUSTERED INDEX [ix_users_username] ON [dbo].[users] ([username] ASC)
GO
