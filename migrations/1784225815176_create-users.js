exports.up = (pgm) => {
  pgm.createType('user_role', ['ADMIN', 'CLIENT']);

  pgm.createTable('users', {
    id: {
      type: 'uuid',
      primaryKey: true,
      default: pgm.func('gen_random_uuid()'),
    },

    name: {
      type: 'varchar(120)',
      notNull: true,
    },

    email: {
      type: 'varchar(255)',
      notNull: true,
      unique: true,
    },

    password_hash: {
      type: 'text',
      notNull: true,
    },

    role: {
      type: 'user_role',
      notNull: true,
      default: 'CLIENT',
    },

    active: {
      type: 'boolean',
      notNull: true,
      default: true,
    },

    email_verified_at: {
      type: 'timestamp with time zone',
      notNull: false,
    },

    created_at: {
      type: 'timestamp with time zone',
      notNull: true,
      default: pgm.func('CURRENT_TIMESTAMP'),
    },

    updated_at: {
      type: 'timestamp with time zone',
      notNull: true,
      default: pgm.func('CURRENT_TIMESTAMP'),
    },
  });

  pgm.createIndex('users', 'email', {
    unique: true,
    name: 'users_email_unique',
  });
};

exports.down = (pgm) => {
  pgm.dropTable('users');
  pgm.dropType('user_role');
};