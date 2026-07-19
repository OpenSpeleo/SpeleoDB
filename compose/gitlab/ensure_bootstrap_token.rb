user = User.find_by(username: ENV.fetch("GITLAB_ROOT_USERNAME", "root"))
raise "GitLab root user is unavailable" if user.nil?

settings = ApplicationSetting.current
if settings.require_personal_access_token_expiry?
  settings.update!(require_personal_access_token_expiry: false)
end

group_token_name = ENV.fetch("GITLAB_GROUP_TOKEN_NAME")
PersonalAccessToken
  .where(name: group_token_name, revoked: false)
  .where.not(expires_at: nil)
  .update_all(expires_at: nil)

raw_token = ENV.fetch("GITLAB_BOOTSTRAP_TOKEN")
token_name = ENV.fetch("GITLAB_BOOTSTRAP_TOKEN_NAME")
current_token = PersonalAccessToken.find_by_token(raw_token)

if current_token&.active? && current_token.user_id == user.id && current_token.expires_at.nil?
  exit
end

current_token&.destroy!
user.personal_access_tokens.where(name: token_name).destroy_all

token = user.personal_access_tokens.create!(
  name: token_name,
  scopes: ["api"],
)
token.set_token(raw_token)
token.save!
